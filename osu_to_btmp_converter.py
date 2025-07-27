#!/usr/bin/env python3
"""
OSU to BTMP Converter
Converts osu! beatmap files (.osu) to custom BTMP format for the rhythm game.
Now supports both classic osu! files and osu!lazer storage.

BTMP Format:
Line 1: Song duration in seconds
Line 2: BPM
Lines 3+: k t b [ht]
  k = key (1=D, 2=F, 3=J, 4=K) 
  t = type (0=regular note, 1=hold note)
  b = beat position (can be fractional like 1.5)
  ht = hold time in beats (only for type 1)
"""

import sys
import os
import re
import platform
import subprocess
import threading
import time
from typing import List, Optional, Dict


class OsuLazerDatabase:
    """Handles osu!lazer database operations."""
    
    def __init__(self, lazer_path: Optional[str] = None):
        self.lazer_path = lazer_path or self.get_default_lazer_path()
        self.files_path = os.path.join(self.lazer_path, "files")
        self.db_path = os.path.join(self.lazer_path, "client.realm")
        
    def get_default_lazer_path(self) -> str:
        """Get the default osu!lazer installation path for the current OS."""
        system = platform.system()
        if system == "Windows":
            appdata = os.getenv('APPDATA')
            if not appdata:
                raise Exception("APPDATA environment variable not found")
            return os.path.join(appdata, 'osu')
        elif system == "Darwin":  # macOS
            return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'osu')
        elif system == "Linux":
            return os.path.join(os.path.expanduser('~'), '.local', 'share', 'osu')
        else:
            raise Exception(f"Unsupported operating system: {system}")
    
    def list_beatmaps(self) -> List[Dict]:
        """List all beatmaps in osu!lazer database."""
        # Note: This is a simplified approach. Real implementation would need
        # to handle Realm database format properly. For now, we'll look for .osu files
        # in the files directory structure.
        beatmaps = []
        
        if not os.path.exists(self.files_path):
            print(f"osu!lazer files directory not found: {self.files_path}")
            return beatmaps
            
        # Walk through hashed file structure
        for root, dirs, files in os.walk(self.files_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    # Try to read file and check if it's a .osu beatmap
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        first_line = f.readline().strip()
                        if first_line.startswith('osu file format v'):
                            # This is a .osu file
                            content = first_line + '\n' + f.read()
                            beatmap_info = self.extract_beatmap_info(content)
                            beatmap_info['file_path'] = file_path
                            beatmap_info['content'] = content
                            beatmaps.append(beatmap_info)
                except:
                    continue
                    
        return beatmaps
    
    def extract_beatmap_info(self, content: str) -> Dict:
        """Extract basic info from .osu file content."""
        info = {'title': 'Unknown', 'artist': 'Unknown', 'version': 'Unknown', 'mode': 0, 'audio_filename': ''}
        
        lines = content.split('\n')
        in_metadata = False
        in_general = False
        
        for line in lines:
            line = line.strip()
            
            if line == '[Metadata]':
                in_metadata = True
                in_general = False
                continue
            elif line == '[General]':
                in_general = True
                in_metadata = False
                continue
            elif line.startswith('[') and line.endswith(']'):
                in_metadata = False
                in_general = False
                continue
                
            if in_metadata and ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if key == 'Title':
                    info['title'] = value
                elif key == 'Artist':
                    info['artist'] = value
                elif key == 'Version':
                    info['version'] = value
            elif in_general and ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if key == 'AudioFilename':
                    info['audio_filename'] = value
            elif line.startswith('Mode:'):
                info['mode'] = int(line.split(':', 1)[1].strip())
                
        return info
    
    def find_audio_file_for_beatmap(self, audio_filename: str, beatmap_path: str) -> Optional[str]:
        """Find audio file in hashed storage using much more aggressive filtering."""
        if not audio_filename:
            return None
            
        print(f"Searching for audio file: {audio_filename}")
        print(f"Expected audio file: {audio_filename}")
        
        # Get file modification time of the beatmap for comparison
        try:
            beatmap_mtime = os.path.getmtime(beatmap_path)
        except:
            beatmap_mtime = None
        
        # Search entire files directory but with much stricter criteria
        all_audio_candidates = []
        
        print("Scanning all audio files (this may take a moment)...")
        file_count = 0
        
        for root, dirs, files in os.walk(self.files_path):
            for file in files:
                file_count += 1
                if file_count % 1000 == 0:
                    print(f"  Scanned {file_count} files...")
                    
                file_path = os.path.join(root, file)
                
                try:
                    # Quick size check first - skip very small files (sound effects)
                    file_size = os.path.getsize(file_path)
                    if file_size < 1000000:  # Skip files under 1MB (likely sound effects)
                        continue
                    
                    # Check if this is an audio file
                    with open(file_path, 'rb') as f:
                        header = f.read(16)
                        
                    audio_info = self.get_audio_info(header, file_path)
                    if not audio_info:
                        continue
                    
                    # Only consider files that are likely full songs (> 1MB)
                    if audio_info['size'] < 1000000:
                        continue
                    
                    # Check modification time proximity (within 1 hour of beatmap)
                    time_score = 0
                    if beatmap_mtime:
                        try:
                            file_mtime = os.path.getmtime(file_path)
                            time_diff = abs(file_mtime - beatmap_mtime)
                            if time_diff < 3600:  # Within 1 hour
                                time_score = 100 - (time_diff / 36)  # Higher score for closer times
                        except:
                            pass
                    
                    # Score based on file size (prefer larger files - full songs)
                    size_score = min(100, audio_info['size'] / 100000)  # Up to 100 points for 10MB+ files
                    
                    # Check if filename might match (case insensitive)
                    name_score = 0
                    audio_base = os.path.splitext(audio_filename.lower())[0]
                    if len(audio_base) > 3:  # Only if we have a meaningful filename
                        # This is tricky since files are hashed, but worth trying
                        pass
                    
                    total_score = size_score + time_score + name_score
                    
                    all_audio_candidates.append({
                        'path': file_path,
                        'format': audio_info['format'],
                        'size': audio_info['size'],
                        'score': total_score,
                        'time_score': time_score,
                        'size_score': size_score
                    })
                        
                except:
                    continue
        
        if not all_audio_candidates:
            print("No suitable audio files found (files > 1MB)")
            return None
        
        # Sort by score (highest first)
        all_audio_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Show top candidates
        top_candidates = all_audio_candidates[:10]  # Show top 10
        
        print(f"\nFound {len(all_audio_candidates)} audio files > 1MB")
        print(f"Top {len(top_candidates)} candidates (sorted by relevance):")
        
        for i, candidate in enumerate(top_candidates):
            size_mb = candidate['size'] / (1024 * 1024)
            print(f"  {i+1}. {candidate['format']} file, {size_mb:.1f}MB (score: {candidate['score']:.1f})")
            print(f"      Time score: {candidate['time_score']:.1f}, Size score: {candidate['size_score']:.1f}")
            print(f"      Path: {candidate['path']}")
        
        # Interactive selection with audio preview
        best_candidate = top_candidates[0]
        print(f"\nMultiple candidates found. Options:")
        print(f"  a) Auto-select (highest score: {best_candidate['score']:.1f})")
        print(f"  p1-p{len(top_candidates)}) Preview and choose specific file")
        print(f"  1-{len(top_candidates)}) Choose specific file (no preview)")
        print(f"  s) Skip audio file")
        
        while True:
            try:
                choice = input("Enter choice (press Enter for auto): ").strip().lower()
                
                if not choice or choice == 'a':
                    print(f"Selected highest scoring file")
                    return best_candidate['path']
                elif choice == 's':
                    print("Skipping audio file")
                    return None
                elif choice.startswith('p') and len(choice) > 1:
                    # Preview mode
                    try:
                        preview_num = int(choice[1:])
                        if 1 <= preview_num <= len(top_candidates):
                            candidate = top_candidates[preview_num - 1]
                            size_mb = candidate['size'] / (1024 * 1024)
                            print(f"\nPreviewing #{preview_num}: {candidate['format']} file, {size_mb:.1f}MB")
                            
                            if self.play_audio_preview(candidate['path'], 15):
                                print(f"\nPreview finished. Use this file? (y/n/c to continue browsing)")
                                confirm = input().strip().lower()
                                if confirm == 'y':
                                    print(f"Selected: {candidate['path']}")
                                    return candidate['path']
                                elif confirm == 'c':
                                    continue  # Back to main menu
                                # 'n' or anything else continues to next choice
                            else:
                                print("Could not preview this file")
                        else:
                            print(f"Invalid number. Choose 1-{len(top_candidates)}")
                    except ValueError:
                        print("Invalid preview command. Use p1, p2, etc.")
                        
                else:
                    # Direct selection without preview
                    try:
                        choice_num = int(choice)
                        if 1 <= choice_num <= len(top_candidates):
                            selected = top_candidates[choice_num - 1]['path']
                            print(f"Selected: {selected}")
                            return selected
                        else:
                            print(f"Invalid choice. Choose 1-{len(top_candidates)}, p1-p{len(top_candidates)}, a, or s")
                    except ValueError:
                        print(f"Invalid input. Use numbers 1-{len(top_candidates)}, p1-p{len(top_candidates)}, 'a' for auto, or 's' to skip")
                        
            except KeyboardInterrupt:
                print("\nUsing auto-selection")
                return best_candidate['path']
    
    def get_audio_info(self, header: bytes, file_path: str) -> Optional[Dict]:
        """Get audio file information from header."""
        try:
            file_size = os.path.getsize(file_path)
            
            # Check for common audio file signatures
            if header.startswith(b'RIFF') and b'WAVE' in header:
                return {'format': 'WAV', 'size': file_size}
            elif header.startswith(b'ID3') or header[0:2] == b'\xff\xfb' or header[0:2] == b'\xff\xf3':
                return {'format': 'MP3', 'size': file_size}
            elif header.startswith(b'OggS'):
                return {'format': 'OGG', 'size': file_size}
            elif header.startswith(b'fLaC'):
                return {'format': 'FLAC', 'size': file_size}
            
            # Skip very small files (likely not full songs)
            if file_size < 1000000:  # 1MB threshold - much more aggressive
                return None
                
        except:
            pass
            
        return None
    
    def play_audio_preview(self, file_path: str, duration: int = 10) -> bool:
        """Play a preview of an audio file for the specified duration."""
        try:
            system = platform.system()
            
            if system == "Darwin":  # macOS
                # Use afplay (built into macOS)
                process = subprocess.Popen(['afplay', file_path])
                
                # Stop after duration seconds
                def stop_playback():
                    time.sleep(duration)
                    try:
                        process.terminate()
                    except:
                        pass
                
                stop_thread = threading.Thread(target=stop_playback)
                stop_thread.daemon = True
                stop_thread.start()
                
                print(f"Playing preview for {duration} seconds... (Press Enter to stop early)")
                
                # Wait for user input or timeout
                import select
                import sys
                
                start_time = time.time()
                while time.time() - start_time < duration:
                    if process.poll() is not None:  # Process ended
                        break
                    
                    # Check for user input (Enter to stop)
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        sys.stdin.readline()  # Consume the input
                        process.terminate()
                        break
                    
                    time.sleep(0.1)
                
                try:
                    process.terminate()
                    process.wait(timeout=1)
                except:
                    pass
                
                return True
                
            elif system == "Windows":
                # Use built-in Windows Media Player command line
                subprocess.run(['powershell', '-c', f'(New-Object Media.SoundPlayer "{file_path}").PlaySync()'], 
                             timeout=duration, check=False)
                return True
                
            elif system == "Linux":
                # Try common Linux audio players
                players = ['aplay', 'paplay', 'ffplay', 'mplayer']
                for player in players:
                    try:
                        if subprocess.run(['which', player], capture_output=True).returncode == 0:
                            subprocess.run([player, file_path], timeout=duration, check=False)
                            return True
                    except:
                        continue
                        
            return False
            
        except Exception as e:
            print(f"Could not play audio: {e}")
            return False


class OsuConverter:
    def __init__(self):
        self.bpm = 120.0
        self.offset = 0
        self.timing_points = []
        self.hit_objects = []
        self.audio_filename = ""
        self.song_length = 0
        self.lazer_db = None
        
    def parse_osu_file(self, filepath: str) -> bool:
        """Parse an .osu file and extract relevant data."""
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except Exception as e:
            print(f"Error reading file: {e}")
            return False
            
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('//'):
                continue
                
            # Check for section headers
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
                continue
                
            # Parse based on current section
            if current_section == "TimingPoints":
                self.parse_timing_point(line)
            elif current_section == "HitObjects":
                self.parse_hit_object(line)
            elif current_section == "General":
                self.parse_general(line)
                
        return True
    
    def parse_osu_content(self, content: str) -> bool:
        """Parse .osu file content directly."""
        lines = content.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('//'):
                continue
                
            # Check for section headers
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
                continue
                
            # Parse based on current section
            if current_section == "TimingPoints":
                self.parse_timing_point(line)
            elif current_section == "HitObjects":
                self.parse_hit_object(line)
            elif current_section == "General":
                self.parse_general(line)
                
        return True
    
    def parse_general(self, line: str):
        """Parse general section for audio filename."""
        if line.startswith("AudioFilename:"):
            self.audio_filename = line.split(":", 1)[1].strip()
    
    def parse_timing_point(self, line: str):
        """Parse timing point data."""
        parts = line.split(',')
        if len(parts) >= 7:
            time = float(parts[0])
            beat_length = float(parts[1])
            uninherited = int(parts[6]) == 1
            
            if uninherited and beat_length > 0:
                # This is a BPM change point
                bpm = 60000 / beat_length
                self.timing_points.append((time, bpm))
                if not hasattr(self, 'first_bpm_set') or not self.first_bpm_set:
                    self.bpm = bpm
                    self.offset = time
                    self.first_bpm_set = True
    
    def parse_hit_object(self, line: str):
        """Parse hit object data."""
        parts = line.split(',')
        if len(parts) >= 4:
            x = int(parts[0])
            time = int(parts[2])
            obj_type = int(parts[3])
            
            # Map X position to key (osu!mania style mapping for 4K)
            # Standard osu! has 512 pixel width, divide into 4 lanes
            key = min(4, max(1, int((x * 4) / 512) + 1))
            
            # Check if it's a hold note (bit 7 set) or spinner (bit 3 set)
            is_hold = (obj_type & 128) != 0  # Bit 7 for osu!mania hold
            is_spinner = (obj_type & 8) != 0  # Bit 3 for spinner
            
            if is_spinner:
                # Skip spinners for now as they don't map well to 4K
                return
                
            if is_hold and len(parts) >= 6:
                # Parse hold note end time
                end_time = int(parts[5].split(':')[0])
                hold_duration = end_time - time
                self.hit_objects.append((time, key, 1, hold_duration))  # Type 1 = hold
            else:
                self.hit_objects.append((time, key, 0, 0))  # Type 0 = regular note
    
    def calculate_beat_position(self, time_ms: float) -> float:
        """Convert millisecond timestamp to beat position."""
        # Find the active BPM at this time
        active_bpm = self.bpm
        active_offset = self.offset
        
        for timing_time, timing_bpm in self.timing_points:
            if timing_time <= time_ms:
                active_bpm = timing_bpm
                active_offset = timing_time
            else:
                break
        
        # Calculate beat position from the timing point
        time_from_timing = time_ms - active_offset
        beats_per_ms = active_bpm / 60000
        beat_position = time_from_timing * beats_per_ms
        
        return max(0, beat_position)
    
    def calculate_song_length(self) -> float:
        """Calculate approximate song length in seconds."""
        if not self.hit_objects:
            return 60.0  # Default fallback
            
        # Get the latest hit object time and add some buffer
        latest_time = max(obj[0] for obj in self.hit_objects)
        return (latest_time / 1000.0) + 5.0  # Add 5 seconds buffer
    
    def convert_to_btmp(self, output_path: str) -> bool:
        """Convert parsed data to BTMP format."""
        if not self.hit_objects:
            print("No hit objects found to convert!")
            return False
            
        # Calculate song length
        self.song_length = self.calculate_song_length()
        
        # Sort hit objects by time
        self.hit_objects.sort(key=lambda x: x[0])
        
        try:
            with open(output_path, 'w') as file:
                # Write header
                file.write("# Converted from .osu file\n")
                file.write(f"{self.song_length:.1f}\n")  # Song length in seconds
                file.write(f"{self.bpm:.0f}\n")  # BPM
                file.write("# Format: k t b [ht]\n")
                file.write("# k=key(1-4), t=type(0=note,1=hold), b=beat, ht=hold_time\n")
                file.write("\n")
                
                # Convert and write hit objects
                for time_ms, key, note_type, hold_duration in self.hit_objects:
                    beat_pos = self.calculate_beat_position(time_ms)
                    
                    if note_type == 1:  # Hold note
                        hold_beats = (hold_duration / 1000.0) * (self.bpm / 60.0)
                        file.write(f"{key} {note_type} {beat_pos:.3f} {hold_beats:.3f}\n")
                    else:  # Regular note
                        file.write(f"{key} {note_type} {beat_pos:.3f}\n")
                        
        except Exception as e:
            print(f"Error writing output file: {e}")
            return False
            
        return True


def list_lazer_beatmaps():
    """List available beatmaps in osu!lazer."""
    try:
        lazer_db = OsuLazerDatabase()
        beatmaps = lazer_db.list_beatmaps()
        
        if not beatmaps:
            print("No beatmaps found in osu!lazer installation.")
            print(f"Searched in: {lazer_db.files_path}")
            return
            
        print(f"Found {len(beatmaps)} beatmaps in osu!lazer:")
        print("=" * 60)
        
        for i, beatmap in enumerate(beatmaps):
            print(f"{i+1:3d}. {beatmap['artist']} - {beatmap['title']} [{beatmap['version']}]")
            if beatmap['mode'] == 3:  # osu!mania
                print("     (osu!mania - recommended for conversion)")
            if beatmap['audio_filename']:
                print(f"     Audio: {beatmap['audio_filename']}")
            
        print("=" * 60)
        print("Use 'python osu_to_btmp_converter.py --lazer <number>' to convert a specific beatmap")
        
    except Exception as e:
        print(f"Error accessing osu!lazer database: {e}")


def convert_from_lazer(beatmap_index: int):
    """Convert a beatmap from osu!lazer storage."""
    try:
        lazer_db = OsuLazerDatabase()
        beatmaps = lazer_db.list_beatmaps()
        
        if not beatmaps:
            print("No beatmaps found in osu!lazer installation.")
            return
            
        if beatmap_index < 1 or beatmap_index > len(beatmaps):
            print(f"Invalid beatmap number. Choose between 1 and {len(beatmaps)}")
            return
            
        selected = beatmaps[beatmap_index - 1]
        print(f"Converting: {selected['artist']} - {selected['title']} [{selected['version']}]")
        
        # Generate output filename
        safe_title = re.sub(r'[^\w\s-]', '', selected['title']).strip()
        safe_artist = re.sub(r'[^\w\s-]', '', selected['artist']).strip()
        safe_version = re.sub(r'[^\w\s-]', '', selected['version']).strip()
        
        output_name = f"{safe_artist} - {safe_title} [{safe_version}]"
        output_path = os.path.join("levels", output_name + '.btmp')
        
        # Ensure levels directory exists
        os.makedirs("levels", exist_ok=True)
        
        # Create converter and process content
        converter = OsuConverter()
        
        if not converter.parse_osu_content(selected['content']):
            print("Failed to parse beatmap content!")
            return
            
        if not converter.convert_to_btmp(output_path):
            print("Failed to convert to .btmp format!")
            return
            
        print(f"Conversion complete!")
        print(f"Output: {output_path}")
        print(f"Song length: {converter.song_length:.1f} seconds")
        print(f"BPM: {converter.bpm:.0f}")
        print(f"Notes converted: {len(converter.hit_objects)}")
        
        # Try to find and copy audio file
        if selected['audio_filename']:
            print(f"Looking for audio file: {selected['audio_filename']}")
            # Find audio file that belongs to this beatmap
            audio_source = lazer_db.find_audio_file_for_beatmap(selected['audio_filename'], selected['file_path'])
            
            if audio_source:
                audio_dest = os.path.join("levels", output_name + '.wav')
                try:
                    import shutil
                    shutil.copy2(audio_source, audio_dest)
                    print(f"Audio file copied to: {audio_dest}")
                except Exception as e:
                    print(f"Warning: Could not copy audio file: {e}")
            else:
                print(f"Warning: Audio file '{selected['audio_filename']}' not found in osu!lazer storage")
        else:
            print("Warning: No audio filename found in beatmap")
        
    except Exception as e:
        print(f"Error converting from osu!lazer: {e}")


def main():
    if len(sys.argv) == 1:
        print("OSU to BTMP Converter")
        print("===================")
        print()
        print("Usage:")
        print("  python osu_to_btmp_converter.py <input.osu>     # Convert classic .osu file")
        print("  python osu_to_btmp_converter.py --list          # List osu!lazer beatmaps")
        print("  python osu_to_btmp_converter.py --lazer <num>   # Convert from osu!lazer")
        sys.exit(0)
    
    if sys.argv[1] == "--list":
        list_lazer_beatmaps()
        return
        
    if sys.argv[1] == "--lazer":
        if len(sys.argv) != 3:
            print("Usage: python osu_to_btmp_converter.py --lazer <beatmap_number>")
            print("Use --list to see available beatmaps")
            sys.exit(1)
            
        try:
            beatmap_num = int(sys.argv[2])
            convert_from_lazer(beatmap_num)
        except ValueError:
            print("Beatmap number must be an integer")
            sys.exit(1)
        return
    
    # Classic .osu file conversion
    input_path = sys.argv[1]
    
    if not os.path.exists(input_path):
        print(f"Error: File '{input_path}' not found!")
        sys.exit(1)
        
    if not input_path.lower().endswith('.osu'):
        print("Error: Input file must be a .osu file!")
        sys.exit(1)
        
    # Generate output filename
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join("levels", base_name + '.btmp')
    
    # Ensure levels directory exists
    os.makedirs("levels", exist_ok=True)
    
    print(f"Converting '{input_path}' to '{output_path}'...")
    
    # Create converter and process file
    converter = OsuConverter()
    
    if not converter.parse_osu_file(input_path):
        print("Failed to parse .osu file!")
        sys.exit(1)
        
    if not converter.convert_to_btmp(output_path):
        print("Failed to convert to .btmp format!")
        sys.exit(1)
        
    print(f"Conversion complete!")
    print(f"Song length: {converter.song_length:.1f} seconds")
    print(f"BPM: {converter.bpm:.0f}")
    print(f"Notes converted: {len(converter.hit_objects)}")
    
    # Copy audio file if it exists
    if converter.audio_filename:
        input_dir = os.path.dirname(input_path)
        audio_source = os.path.join(input_dir, converter.audio_filename)
        
        if os.path.exists(audio_source):
            # Copy to levels directory with .wav extension
            audio_dest = os.path.join("levels", base_name + '.wav')
            
            try:
                import shutil
                shutil.copy2(audio_source, audio_dest)
                print(f"Audio file copied to: {audio_dest}")
            except Exception as e:
                print(f"Warning: Could not copy audio file: {e}")
        else:
            print(f"Warning: Audio file '{converter.audio_filename}' not found in source directory")


if __name__ == "__main__":
    main()
