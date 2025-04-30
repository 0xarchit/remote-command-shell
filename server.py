import socket
import threading
import subprocess
import struct
import platform
import signal
import time
import os
import glob
import shlex

# Use localhost instead of 0.0.0.0 to match client configuration
HOST = 'localhost'
PORT = 5000

# Handle timeouts for long-running commands
COMMAND_TIMEOUT = 60  # seconds - increased for streaming commands like ping
STREAM_CHUNK_SIZE = 1024  # bytes to send in each chunk
STREAM_INTERVAL = 0.1  # seconds between stream checks

# Commands that should stream their output
STREAMING_COMMANDS = ['ping', 'tracert', 'traceroute', 'wget', 'curl', 'nslookup']

# Common commands for tab completion (platform-specific)
COMMON_WINDOWS_COMMANDS = [
    "dir", "cd", "copy", "del", "echo", "exit", "find", "findstr", "help", 
    "ipconfig", "mkdir", "move", "net", "netstat", "ping", "powershell", 
    "rd", "rmdir", "systeminfo", "tasklist", "taskkill", "time", "type", "ver"
]

COMMON_UNIX_COMMANDS = [
    "ls", "cd", "cp", "rm", "echo", "exit", "find", "grep", "help", 
    "ifconfig", "mkdir", "mv", "netstat", "ping", "ps", "pwd", 
    "rm", "rmdir", "ssh", "sudo", "cat", "uname", "whoami"
]

def is_streaming_command(cmd):
    """Check if a command should stream its output"""
    cmd_base = cmd.strip().split()[0].lower()
    # Special case for "ping" - force to be streamed
    if cmd_base == "ping":
        return True
    # Added extra logging to debug the streaming command detection
    print(f"Command base: {cmd_base}, Is streaming: {any(stream_cmd in cmd_base for stream_cmd in STREAMING_COMMANDS)}")
    return any(stream_cmd in cmd_base for stream_cmd in STREAMING_COMMANDS)

def stream_command_output(cmd, system, conn):
    """Execute a command and stream its output in real-time"""
    try:
        # Prepare special message header to indicate streaming mode
        stream_start = "--- STREAM_START ---\n".encode('utf-8')
        conn.sendall(struct.pack('>I', len(stream_start)))
        conn.sendall(stream_start)
        
        if system.lower() == 'windows':
            # For Windows
            process = subprocess.Popen(
                ["cmd", "/c", cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,  # Binary mode for better streaming
                bufsize=0,   # Unbuffered
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            # For Unix-based systems
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,  # Binary mode
                bufsize=0    # Unbuffered
            )

        # Set non-blocking mode
        for pipe in [process.stdout, process.stderr]:
            if pipe:
                os.set_blocking(pipe.fileno(), False)
                
        # Track if we've sent any data yet
        sent_data = False
        start_time = time.time()
        
        # Stream while process is alive
        while process.poll() is None:
            # Check timeout
            if time.time() - start_time > COMMAND_TIMEOUT:
                process.kill()
                timeout_msg = f"\n\nCommand timed out after {COMMAND_TIMEOUT} seconds".encode('utf-8')
                conn.sendall(struct.pack('>I', len(timeout_msg)))
                conn.sendall(timeout_msg)
                return
                
            # Check for output
            ready_pipes = []
            
            # Try to read from pipes that are ready
            output_data = b""
            
            # Try to read from stdout
            try:
                stdout_data = process.stdout.read(STREAM_CHUNK_SIZE)
                if stdout_data:
                    output_data += stdout_data
                    sent_data = True
            except (IOError, BrokenPipeError):
                pass
                
            # Try to read from stderr
            try:
                stderr_data = process.stderr.read(STREAM_CHUNK_SIZE)
                if stderr_data:
                    output_data += stderr_data
                    sent_data = True
            except (IOError, BrokenPipeError):
                pass
                
            # If we got data, send it
            if output_data:
                conn.sendall(struct.pack('>I', len(output_data)))
                conn.sendall(output_data)
            
            # Prevent CPU overload with a small sleep
            time.sleep(STREAM_INTERVAL)

        # Get any remaining output
        remaining_output = b""
        try:
            stdout, stderr = process.communicate(timeout=1)
            if stdout:
                remaining_output += stdout
            if stderr:
                remaining_output += stderr
        except:
            pass
            
        # Send remaining output if any
        if remaining_output:
            conn.sendall(struct.pack('>I', len(remaining_output)))
            conn.sendall(remaining_output)
            
        # Send exit code
        exit_msg = f"\n\nCommand exit code: {process.returncode}".encode('utf-8')
        conn.sendall(struct.pack('>I', len(exit_msg)))
        conn.sendall(exit_msg)
        
        # Check if we sent any data at all
        if not sent_data and process.returncode == 0:
            # Command completed successfully but produced no output
            no_output_msg = "Command executed but produced no output.\n".encode('utf-8')
            conn.sendall(struct.pack('>I', len(no_output_msg)))
            conn.sendall(no_output_msg)
        
        # Send stream end marker
        stream_end = "--- STREAM_END ---\n".encode('utf-8')
        conn.sendall(struct.pack('>I', len(stream_end)))
        conn.sendall(stream_end)
            
    except Exception as e:
        # Send error message
        error_msg = f"Error streaming command: {str(e)}\n".encode('utf-8')
        try:
            conn.sendall(struct.pack('>I', len(error_msg)))
            conn.sendall(error_msg)
            
            # Send stream end marker
            stream_end = "--- STREAM_END ---\n".encode('utf-8')
            conn.sendall(struct.pack('>I', len(stream_end)))
            conn.sendall(stream_end)
        except:
            pass

def execute_command(cmd, system):
    """Execute a command and return its output with proper handling for different platforms"""
    try:
        # Special handling for interactive commands
        if cmd.strip().lower() == "cmd":
            return "The 'cmd' command starts an interactive shell which isn't supported directly.\nTry specific commands instead like 'dir', 'echo', etc.\n\nCommand exit code: 0"
        
        # Special handling for cd with no arguments
        if cmd.strip().lower() == "cd":
            if system.lower() == 'windows':
                # On Windows, return current directory using echo %cd%
                process = subprocess.Popen(
                    ["cmd", "/c", "echo %cd%"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                output, error = process.communicate(timeout=COMMAND_TIMEOUT)
                return f"Current directory: {output}\n\nCommand exit code: {process.returncode}"
            else:
                # On Unix, return current directory using pwd
                process = subprocess.Popen(
                    ["pwd"], 
                    shell=True,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True
                )
                output, error = process.communicate(timeout=COMMAND_TIMEOUT)
                return f"Current directory: {output}\n\nCommand exit code: {process.returncode}"
                
        # Handle ls on Windows as dir
        if cmd.strip().lower() == "ls" and system.lower() == 'windows':
            cmd = "dir"
            
        # Normal command processing
        if system.lower() == 'windows':
            # For Windows, use cmd /c for non-interactive commands
            process = subprocess.Popen(
                ["cmd", "/c", cmd], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            # For Unix-based systems
            process = subprocess.Popen(
                cmd, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            
        # Use timeout to avoid hanging on long-running commands
        output, error = process.communicate(timeout=COMMAND_TIMEOUT)
        result = output + error
        
        # Check if output is empty but command should produce output
        if not result.strip() and cmd.strip().lower() in ["dir", "ls"]:
            result = "Command executed but returned no output. This might be due to directory permissions or an empty directory."
        
        # Include exit code information
        result += f"\nCommand exit code: {process.returncode}"
        return result
    except subprocess.TimeoutExpired:
        # Kill the process if it times out
        if process:
            if system.lower() == 'windows':
                process.kill()
            else:
                process.send_signal(signal.SIGKILL)
        return f"Command timed out after {COMMAND_TIMEOUT} seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"

def handle_completion_request(cmd, system):
    """Handle special command completion requests from the client"""
    if cmd.startswith("__complete_cmd__"):
        # Command completion
        prefix = cmd[16:].strip()  # Extract the prefix to complete
        return get_command_completions(prefix, system)
    elif cmd.startswith("__complete_path__"):
        # Path completion
        path_prefix = cmd[17:].strip()  # Extract the path prefix
        return get_path_completions(path_prefix, system)
    return None

def get_command_completions(prefix, system):
    """Get command completions based on prefix and system"""
    completions = []
    
    # Add common commands based on the operating system
    if system.lower() == 'windows':
        common_commands = COMMON_WINDOWS_COMMANDS
    else:
        common_commands = COMMON_UNIX_COMMANDS
        
    # Filter commands that match the prefix
    for cmd in common_commands:
        if cmd.startswith(prefix.lower()):
            completions.append(cmd)
            
    # Try to get additional completions from the system
    try:
        if system.lower() == 'windows':
            # Get executable files in PATH
            paths = os.environ.get('PATH', '').split(';')
            for path in paths:
                if os.path.exists(path):
                    for file in os.listdir(path):
                        if file.lower().startswith(prefix.lower()) and (
                            file.endswith('.exe') or file.endswith('.bat') or file.endswith('.cmd')
                        ):
                            base_name = os.path.splitext(file)[0]
                            if base_name not in completions:
                                completions.append(base_name)
        else:
            # For Unix, use compgen built-in
            process = subprocess.Popen(
                f"compgen -c {shlex.quote(prefix)}", 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            output, _ = process.communicate(timeout=2)
            for line in output.splitlines():
                if line and line not in completions:
                    completions.append(line)
    except:
        # Fallback to basic completion if system methods fail
        pass
        
    # Format the response for the client
    if completions:
        return f"__COMPLETIONS__:{','.join(completions)}"
    else:
        return f"__COMPLETIONS__:"

def get_path_completions(path_prefix, system):
    """Get path completions based on prefix"""
    completions = []
    
    # Normalize path based on system
    if system.lower() == 'windows':
        # Handle Windows paths with backslashes
        norm_prefix = os.path.normpath(path_prefix)
        # Check if it's a directory pattern or file pattern
        if norm_prefix.endswith('\\') or norm_prefix.endswith('/'):
            pattern = os.path.join(norm_prefix, '*')
        else:
            pattern = norm_prefix + '*'
    else:
        # Handle Unix paths
        norm_prefix = os.path.normpath(path_prefix)
        if norm_prefix.endswith('/'):
            pattern = os.path.join(norm_prefix, '*')
        else:
            pattern = norm_prefix + '*'
    
    # Use glob to find matching paths
    try:
        matching_paths = glob.glob(pattern)
        
        for path in matching_paths:
            # For directories, add trailing separator
            if os.path.isdir(path):
                if system.lower() == 'windows':
                    path += '\\'
                else:
                    path += '/'
                    
            # Add to completions
            completions.append(path)
    except:
        pass
        
    # Format the response for the client
    if completions:
        return f"__COMPLETIONS__:{','.join(completions)}"
    else:
        return f"__COMPLETIONS__:"

def handle_client(conn, addr):
    print(f'Connected by {addr}')
    system = platform.system()
    with conn:
        while True:
            try:
                # Receive command terminated by newline
                data = b''
                while not data.endswith(b'\n'):
                    packet = conn.recv(1024)
                    if not packet:
                        print(f"Client {addr} disconnected abruptly")
                        return
                    data += packet
                
                cmd = data.decode().strip()
                print(f"Received command: {cmd}")
                
                if cmd.lower() in ('exit', 'quit'):
                    print(f'Client {addr} disconnected')
                    break

                # Check if this is a completion request
                if cmd.startswith("__complete"):
                    completion_result = handle_completion_request(cmd, system)
                    if completion_result:
                        result_bytes = completion_result.encode('utf-8', errors='replace')
                        conn.sendall(struct.pack('>I', len(result_bytes)))
                        conn.sendall(result_bytes)
                        continue
                
                # Check if this should be a streaming command
                if is_streaming_command(cmd):
                    # Handle streaming command in a separate function
                    stream_command_output(cmd, system, conn)
                else:
                    # Execute the command with improved handling
                    result = execute_command(cmd, system)
                    if not result:
                        result = '\n'
                    
                    # Send length prefix then data
                    result_bytes = result.encode('utf-8', errors='replace')
                    conn.sendall(struct.pack('>I', len(result_bytes)))
                    conn.sendall(result_bytes)
                
            except ConnectionResetError:
                print(f"Connection reset by client {addr}")
                break
            except Exception as e:
                print(f"Error handling client {addr}: {e}")
                break

    print(f'Connection closed for {addr}')


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f'Server listening on {HOST}:{PORT}')
        
        try:
            while True:
                conn, addr = s.accept()
                client_thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
                client_thread.start()
        except KeyboardInterrupt:
            print("Server shutting down...")
        except Exception as e:
            print(f"Server error: {e}")


if __name__ == '__main__':
    main()