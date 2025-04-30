import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import socket
import struct
import threading
import tkinter.filedialog as fd
import time
import platform
from datetime import datetime

class RemoteClient:
    def __init__(self):
        # Setup GUI first so we can display connection errors in the UI
        self.root = tk.Tk()
        self.root.title("Remote Command Terminal")
        self.root.geometry("900x600")
        self.root.minsize(800, 500)  # Set minimum window size
        
        # Set app icon (could be customized)
        try:
            self.root.iconbitmap("terminal.ico")
        except:
            pass  # Icon not found, use default
            
        # Theme configuration and colors
        self.theme_mode = "dark"  # Default to dark theme
        self.bg_color = "#1e1e1e"
        self.text_bg = "#2d2d2d"
        self.text_fg = "#f0f0f0"
        self.accent_color = "#007acc"
        self.success_color = "#4EC9B0"
        self.error_color = "#F44747"
        self.button_bg = "#3c3c3c"
        self.button_fg = "#f0f0f0"
        
        # Server configuration
        self.host = 'localhost'
        self.port = 5000
        
        # Command history
        self.cmd_history = []
        self.history_index = 0
        self.current_path = "~"  # Default path indicator
        
        # Add common command shortcuts (platform-specific)
        self.common_commands = {
            "List directory": "dir" if platform.system().lower() == "windows" else "ls",
            "Network config": "ipconfig" if platform.system().lower() == "windows" else "ifconfig",
            "System info": "systeminfo" if platform.system().lower() == "windows" else "uname -a",
            "Process list": "tasklist" if platform.system().lower() == "windows" else "ps aux",
            "Clear screen": "cls" if platform.system().lower() == "windows" else "clear"
        }
        
        # Session logging
        self.logging_enabled = False
        self.log_file = None
        
        # Setup UI elements with the new styling
        self.create_widgets()
        
        # Initialize connection status as disconnected
        self.sock = None
        self.server_info = {"system": "Unknown", "version": "Unknown"}
        
        # Try to establish connection
        self.toggle_connection()
        
        # Set up event bindings
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Start the UI main loop
        self.root.mainloop()

    def create_widgets(self):
        # Configure root window style
        self.root.configure(bg=self.bg_color)
        
        # Main content frame
        main_frame = tk.Frame(self.root, bg=self.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Top panel with connection info and buttons
        top_frame = tk.Frame(main_frame, bg=self.bg_color)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Connection status with icon
        status_frame = tk.Frame(top_frame, bg=self.bg_color)
        status_frame.pack(side=tk.LEFT)
        
        self.status_dot = tk.Canvas(status_frame, width=12, height=12, bg=self.bg_color, 
                                   highlightthickness=0)
        self.status_dot.create_oval(2, 2, 10, 10, fill=self.error_color, outline="")
        self.status_dot.pack(side=tk.LEFT, padx=(0, 5))
        
        self.status_frame = tk.Frame(status_frame, bg=self.bg_color)
        self.status_frame.pack(side=tk.LEFT)
        
        self.status_label = tk.Label(self.status_frame, 
                                    text="Disconnected", 
                                    bg=self.bg_color, fg=self.error_color,
                                    font=("Consolas", 10, "bold"))
        self.status_label.pack(anchor="w")
        
        self.server_info_label = tk.Label(self.status_frame,
                                         text="Server: Not connected",
                                         bg=self.bg_color, fg=self.text_fg,
                                         font=("Consolas", 8))
        self.server_info_label.pack(anchor="w")
        
        # Right side buttons
        buttons_frame = tk.Frame(top_frame, bg=self.bg_color)
        buttons_frame.pack(side=tk.RIGHT)
        
        self.conn_btn = tk.Button(buttons_frame, text="Connect", bg=self.button_bg,
                                 fg=self.button_fg, font=("Consolas", 9),
                                 width=10, relief=tk.FLAT, command=self.toggle_connection)
        self.conn_btn.pack(side=tk.LEFT, padx=5)
        
        # Add server config button
        config_btn = tk.Button(buttons_frame, text="Server Config", bg=self.button_bg,
                              fg=self.button_fg, font=("Consolas", 9),
                              width=12, relief=tk.FLAT, command=self.create_server_config_dialog)
        config_btn.pack(side=tk.LEFT, padx=5)
        
        # Add theme toggle button
        self.theme_btn = tk.Button(buttons_frame, text="Light Theme", bg=self.button_bg,
                                 fg=self.button_fg, font=("Consolas", 9),
                                 width=12, relief=tk.FLAT, command=self.toggle_theme)
        self.theme_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = tk.Button(buttons_frame, text="Clear Output", bg=self.button_bg,
                             fg=self.button_fg, font=("Consolas", 9),
                             width=12, relief=tk.FLAT, command=self.clear_output)
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        save_btn = tk.Button(buttons_frame, text="Save Output", bg=self.button_bg,
                            fg=self.button_fg, font=("Consolas", 9),
                            width=12, relief=tk.FLAT, command=self.save_output)
        save_btn.pack(side=tk.LEFT, padx=5)
        
        # Split view with output and history
        self.paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Command output panel
        output_frame = tk.Frame(self.paned_window, bg=self.bg_color)
        
        # Path indicator banner
        path_frame = tk.Frame(output_frame, bg=self.accent_color)
        path_frame.pack(fill=tk.X)
        
        path_controls = tk.Frame(path_frame, bg=self.accent_color)
        path_controls.pack(fill=tk.X)
        
        self.path_label = tk.Label(path_controls, text="Current path: ~", 
                                  bg=self.accent_color, fg="white",
                                  font=("Consolas", 9, "bold"), anchor="w", padx=5, pady=2)
        self.path_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Add browse button
        browse_btn = tk.Button(path_controls, text="📁", bg=self.accent_color,
                              fg="white", font=("Consolas", 9, "bold"), padx=5,
                              relief=tk.FLAT, command=self.open_file_browser)
        browse_btn.pack(side=tk.RIGHT)
        
        # Output display with syntax highlighting style
        self.text_area = ScrolledText(output_frame, bg=self.text_bg, fg=self.text_fg,
                                     insertbackground=self.text_fg, font=("Consolas", 10),
                                     selectbackground=self.accent_color, padx=10, pady=10,
                                     wrap=tk.WORD)
        self.text_area.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Timestamp everything in output
        self.text_area.tag_configure("timestamp", foreground="#808080", font=("Consolas", 8))
        self.text_area.tag_configure("command", foreground="#569CD6", font=("Consolas", 10, "bold"))
        self.text_area.tag_configure("error", foreground=self.error_color)
        self.text_area.tag_configure("success", foreground=self.success_color)
        
        # Command entry with prompt
        entry_frame = tk.Frame(output_frame, bg=self.bg_color)
        entry_frame.pack(fill=tk.X)
        
        prompt_label = tk.Label(entry_frame, text=">", bg=self.bg_color, 
                               fg=self.accent_color, font=("Consolas", 12, "bold"))
        prompt_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.entry = tk.Entry(entry_frame, bg=self.text_bg, fg=self.text_fg,
                             insertbackground=self.text_fg, font=("Consolas", 11),
                             relief=tk.FLAT, bd=5)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        
        # Bind entry keys
        self.entry.bind('<Return>', self.send_command)
        self.entry.bind('<Up>', self.history_up)
        self.entry.bind('<Down>', self.history_down)
        self.entry.bind('<Tab>', self.tab_completion)
        
        send_btn = tk.Button(entry_frame, text="Send", bg=self.accent_color,
                            fg="white", font=("Consolas", 9, "bold"),
                            width=10, relief=tk.FLAT, command=self.send_command)
        send_btn.pack(side=tk.RIGHT, padx=5)
        self.send_btn = send_btn
        
        # Right-side panel with history and shortcuts
        right_panel = ttk.Notebook(self.paned_window)
        
        # History tab
        history_frame = tk.Frame(right_panel, bg=self.text_bg)
        right_panel.add(history_frame, text="History")
        
        history_label = tk.Label(history_frame, text="Command History", bg=self.text_bg,
                                fg=self.text_fg, font=("Consolas", 10, "bold"))
        history_label.pack(anchor="w", padx=10, pady=5)
        
        # Add clear history button
        clear_history_btn = tk.Button(history_frame, text="Clear History", bg=self.button_bg,
                                    fg=self.button_fg, font=("Consolas", 9),
                                    relief=tk.FLAT, command=self.clear_history)
        clear_history_btn.pack(anchor="e", padx=10, pady=2)
        
        self.history_listbox = tk.Listbox(history_frame, bg=self.text_bg, fg=self.text_fg,
                                         font=("Consolas", 9), bd=0, relief=tk.FLAT,
                                         selectbackground=self.accent_color)
        self.history_listbox.pack(fill=tk.BOTH, expand=True, padx=10)
        self.history_listbox.bind('<Double-Button-1>', self.use_history_item)
        
        # Shortcuts tab
        shortcuts_frame = tk.Frame(right_panel, bg=self.text_bg)
        right_panel.add(shortcuts_frame, text="Shortcuts")
        
        shortcuts_label = tk.Label(shortcuts_frame, text="Common Commands", bg=self.text_bg,
                                  fg=self.text_fg, font=("Consolas", 10, "bold"))
        shortcuts_label.pack(anchor="w", padx=10, pady=5)
        
        # Add common command buttons
        for name, cmd in self.common_commands.items():
            btn = tk.Button(shortcuts_frame, text=name, bg=self.button_bg,
                          fg=self.button_fg, font=("Consolas", 9),
                          relief=tk.FLAT, anchor="w", padx=10,
                          command=lambda c=cmd: self.use_shortcut(c))
            btn.pack(fill=tk.X, padx=10, pady=2)
            
        # File Explorer tab
        file_explorer_frame = tk.Frame(right_panel, bg=self.text_bg)
        right_panel.add(file_explorer_frame, text="Files")
        
        explorer_label = tk.Label(file_explorer_frame, text="Remote Files", bg=self.text_bg,
                                fg=self.text_fg, font=("Consolas", 10, "bold"))
        explorer_label.pack(anchor="w", padx=10, pady=5)
        
        # Add refresh button
        refresh_btn = tk.Button(file_explorer_frame, text="Refresh", bg=self.button_bg,
                              fg=self.button_fg, font=("Consolas", 9),
                              relief=tk.FLAT, command=self.refresh_file_browser)
        refresh_btn.pack(anchor="e", padx=10, pady=2)
        
        # File browser frame with directory tree
        browser_frame = tk.Frame(file_explorer_frame, bg=self.text_bg)
        browser_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.file_tree = ttk.Treeview(browser_frame)
        self.file_tree.pack(fill=tk.BOTH, expand=True)
        
        # Configure columns for file browser
        self.file_tree["columns"] = ("size", "modified")
        self.file_tree.column("#0", width=200, minwidth=150, stretch=tk.YES)
        self.file_tree.column("size", width=80, minwidth=50, stretch=tk.NO)
        self.file_tree.column("modified", width=120, minwidth=100, stretch=tk.NO)
        
        # Configure headers
        self.file_tree.heading("#0", text="Name", anchor=tk.W)
        self.file_tree.heading("size", text="Size", anchor=tk.W)
        self.file_tree.heading("modified", text="Modified", anchor=tk.W)
        
        # Bind file browser events
        self.file_tree.bind("<Double-1>", self.file_browser_action)
        
        # Settings tab
        settings_frame = tk.Frame(right_panel, bg=self.text_bg)
        right_panel.add(settings_frame, text="Settings")
        
        settings_label = tk.Label(settings_frame, text="Session Settings", bg=self.text_bg,
                                fg=self.text_fg, font=("Consolas", 10, "bold"))
        settings_label.pack(anchor="w", padx=10, pady=5)
        
        # Add session logging toggle
        logging_frame = tk.Frame(settings_frame, bg=self.text_bg)
        logging_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.logging_var = tk.BooleanVar(value=self.logging_enabled)
        logging_cb = tk.Checkbutton(logging_frame, text="Session Logging", 
                                  variable=self.logging_var,
                                  bg=self.text_bg, fg=self.text_fg,
                                  selectcolor=self.bg_color,
                                  command=self.toggle_logging)
        logging_cb.pack(side=tk.LEFT)
        
        logging_path_btn = tk.Button(logging_frame, text="Set Log File", bg=self.button_bg,
                                   fg=self.button_fg, font=("Consolas", 9),
                                   relief=tk.FLAT, command=self.select_log_file)
        logging_path_btn.pack(side=tk.RIGHT)
        
        # Add panels to paned window
        self.paned_window.add(output_frame, weight=3)
        self.paned_window.add(right_panel, weight=1)
        
        # Focus the entry
        self.entry.focus_set()

    def send_command(self, event=None):
        cmd = self.entry.get().strip()
        if not cmd or not self.sock:
            return
            
        # Record and display command
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.cmd_history.append(cmd)
        self.history_index = len(self.cmd_history)
        
        # Update history listbox
        self.history_listbox.insert(0, f"{timestamp} > {cmd}")
        
        # Display command in output with timestamp
        self.text_area.configure(state='normal')
        self.text_area.insert(tk.END, f"\n[{timestamp}] ", "timestamp")
        self.text_area.insert(tk.END, f"> {cmd}\n", "command")
        self.text_area.see(tk.END)
        self.text_area.configure(state='disabled')
        
        # Log the command if logging is enabled
        if self.logging_enabled:
            self.log_to_file(cmd, is_command=True)
        
        # Clear entry
        self.entry.delete(0, tk.END)
        
        # Execute command in thread
        threading.Thread(target=self.handle_command, args=(cmd,), daemon=True).start()
        
    def handle_command(self, cmd):
        try:
            # Update UI to show processing
            self.update_status("Processing...", "#FFA500")
            
            # Special command handling: cd to update current path
            if cmd.strip().startswith("cd "):
                self.handle_change_directory(cmd)
                return
                
            # Send command with newline
            self.sock.sendall((cmd + '\n').encode())

            # First chunk might tell us if this is a streaming command
            raw_len = self.recvall(4)
            if not raw_len:
                self.display_output("Connection lost while waiting for response.\n", "error")
                self.toggle_connection()  # Disconnect
                return
                
            length = struct.unpack('>I', raw_len)[0]

            # Receive the first data chunk
            data = self.recvall(length)
            output = data.decode(errors='replace')
            
            # Check if this is a streaming command
            if "--- STREAM_START ---" in output:
                # Handle streaming mode
                self.display_output("Live streaming output:\n", "timestamp")
                
                # Remove the stream start marker
                output = output.replace("--- STREAM_START ---\n", "")
                if output:
                    self.display_output(output)
                    
                # Keep receiving chunks until we get the stream end marker
                streaming = True
                self.text_area.configure(state='normal')
                
                while streaming:
                    try:
                        # Get next chunk length
                        raw_len = self.recvall(4)
                        if not raw_len:
                            break
                        
                        length = struct.unpack('>I', raw_len)[0]
                        
                        # Get chunk data
                        data = self.recvall(length)
                        chunk = data.decode(errors='replace')
                        
                        # Check for stream end marker
                        if "--- STREAM_END ---" in chunk:
                            streaming = False
                            # Remove the marker from the output
                            chunk = chunk.replace("--- STREAM_END ---\n", "")
                            
                        # Display the chunk if not empty
                        if chunk:
                            # Check for exit code in output
                            if "exit code: 0" in chunk.lower():
                                self.text_area.insert(tk.END, chunk, "success")
                            elif "exit code:" in chunk.lower():
                                self.text_area.insert(tk.END, chunk, None)
                            else:
                                self.text_area.insert(tk.END, chunk)
                            
                            self.text_area.see(tk.END)
                            # Update UI immediately without waiting
                            self.text_area.update()
                            
                    except Exception as e:
                        self.text_area.insert(tk.END, f"\nError receiving stream: {e}\n", "error")
                        self.text_area.see(tk.END)
                        streaming = False
                        
                self.text_area.configure(state='disabled')
                
            else:
                # Normal non-streaming command
                # Check for exit code in output
                success = "exit code: 0" in output.lower()
                tag = "success" if success else None
                
                # Display output
                self.display_output(output, tag)
            
            # Reset status
            self.update_status("Connected", self.success_color)
            
        except Exception as e:
            self.display_output(f"Error: {e}\n", "error")
            self.update_status("Error", self.error_color)

    def handle_change_directory(self, cmd):
        """Handle cd command locally to track current directory"""
        # Extract the directory argument
        parts = cmd.split(" ", 1)
        if len(parts) < 2:
            self.display_output("Usage: cd <directory>\n", "error")
            return
            
        dir_arg = parts[1].strip()
        
        # Track directory (simple implementation - could be improved)
        if dir_arg == "..":
            if "/" in self.current_path and self.current_path != "/":
                self.current_path = self.current_path.rsplit("/", 1)[0]
            elif "\\" in self.current_path and self.current_path != "\\":
                self.current_path = self.current_path.rsplit("\\", 1)[0]
        elif dir_arg == "~" or dir_arg == "%USERPROFILE%":
            self.current_path = "~"
        else:
            if dir_arg.startswith("/") or (len(dir_arg) > 1 and dir_arg[1] == ":"):
                # Absolute path
                self.current_path = dir_arg
            else:
                # Relative path
                if self.current_path == "~":
                    self.current_path = dir_arg
                else:
                    separator = "/" if "/" in self.current_path else "\\"
                    self.current_path = f"{self.current_path}{separator}{dir_arg}"
        
        # Update path display
        self.path_label.config(text=f"Current path: {self.current_path}")
        
        # Send actual cd command to server
        self.handle_command(cmd)

    def recvall(self, n):
        """Reliably receive n bytes from socket"""
        data = b''
        while len(data) < n:
            packet = self.sock.recv(n - len(data))
            if not packet:
                break
            data += packet
        return data

    def display_output(self, text, tag=None):
        """Display output in text area with optional tag"""
        self.text_area.configure(state='normal')
        if tag:
            self.text_area.insert(tk.END, text, tag)
        else:
            self.text_area.insert(tk.END, text)
        self.text_area.see(tk.END)
        self.text_area.configure(state='disabled')

    def history_up(self, event=None):
        """Navigate command history up"""
        if self.cmd_history and self.history_index > 0:
            self.history_index -= 1
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self.cmd_history[self.history_index])
        return 'break'  # Prevent default key handling

    def history_down(self, event=None):
        """Navigate command history down"""
        if self.cmd_history and self.history_index < len(self.cmd_history) - 1:
            self.history_index += 1
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self.cmd_history[self.history_index])
        else:
            self.history_index = len(self.cmd_history)
            self.entry.delete(0, tk.END)
        return 'break'  # Prevent default key handling
        
    def tab_completion(self, event=None):
        """Tab completion with server-side suggestions"""
        current_text = self.entry.get()
        
        if not current_text or not self.sock:
            return 'break'
        
        try:
            # Request server-side completion suggestions
            if current_text.startswith('cd ') and len(current_text) > 3:
                # For directory completion
                path_prefix = current_text[3:]
                self.get_server_completion(f"__complete_path__ {path_prefix}")
            else:
                # For command completion
                self.get_server_completion(f"__complete_cmd__ {current_text}")
                
            # Also check local history and shortcuts
            local_matches = []
            for cmd in self.cmd_history:
                if cmd.startswith(current_text):
                    local_matches.append(cmd)
                    
            # Check common commands
            for cmd_name, cmd in self.common_commands.items():
                if cmd.startswith(current_text):
                    local_matches.append(cmd)
                    
            if len(local_matches) == 1:
                # If single match locally, complete it
                self.entry.delete(0, tk.END)
                self.entry.insert(0, local_matches[0])
            elif len(local_matches) > 1:
                # Show options
                self.display_output("\nLocal completion options:\n")
                for match in local_matches:
                    self.display_output(f"  {match}\n")
                    
        except Exception as e:
            # Fallback to basic completion if server-side fails
            print(f"Completion error: {e}")
            
        return 'break'  # Prevent default tab behavior
        
    def get_server_completion(self, cmd):
        """Get command completion suggestions from server"""
        try:
            # Send special completion command
            self.sock.sendall((cmd + '\n').encode())
            
            # Get response
            raw_len = self.recvall(4)
            if not raw_len:
                return
                
            length = struct.unpack('>I', raw_len)[0]
            data = self.recvall(length)
            output = data.decode(errors='replace')
            
            # Process completion suggestions
            if output.startswith("__COMPLETIONS__:"):
                suggestions = output[15:].strip().split(',')
                if suggestions and suggestions[0]:
                    if len(suggestions) == 1:
                        # Auto-complete with the single suggestion
                        current = self.entry.get()
                        if current.startswith('cd '):
                            self.entry.delete(0, tk.END)
                            self.entry.insert(0, f"cd {suggestions[0]}")
                        else:
                            self.entry.delete(0, tk.END)
                            self.entry.insert(0, suggestions[0])
                    else:
                        # Display multiple suggestions
                        self.display_output("\nServer suggestions:\n")
                        for suggestion in suggestions:
                            self.display_output(f"  {suggestion}\n")
        except:
            pass

    def use_history_item(self, event=None):
        """Use command from history on double-click"""
        selection = self.history_listbox.curselection()
        if selection:
            item = self.history_listbox.get(selection[0])
            # Extract command from history item (removes timestamp)
            cmd = item.split("> ", 1)[1] if "> " in item else item
            self.entry.delete(0, tk.END)
            self.entry.insert(0, cmd)
            self.entry.focus_set()

    def use_shortcut(self, cmd):
        """Insert shortcut command into entry"""
        self.entry.delete(0, tk.END)
        self.entry.insert(0, cmd)
        self.entry.focus_set()

    def on_close(self):
        """Handle window close"""
        if self.sock:
            try:
                self.sock.sendall(b'exit\n')
                time.sleep(0.1)  # Give server a moment to process exit
                self.sock.close()
            except:
                pass
        self.root.destroy()

    def clear_output(self):
        """Clear output text area"""
        self.text_area.configure(state='normal')
        self.text_area.delete(1.0, tk.END)
        self.text_area.configure(state='disabled')

    def save_output(self):
        """Save output to file"""
        content = self.text_area.get(1.0, tk.END)
        path = fd.asksaveasfilename(
            defaultextension='.txt', 
            filetypes=[('Text', '*.txt'), ('Log File', '*.log'), ('All Files', '*.*')],
            title="Save Terminal Output"
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            # Show a success message in status bar
            self.update_status(f"Saved to {path.split('/')[-1]}", self.success_color)
            # Reset status after a delay
            self.root.after(3000, lambda: self.update_status(
                "Connected" if self.sock else "Disconnected", 
                self.success_color if self.sock else self.error_color
            ))
   
    def toggle_connection(self):
        """Toggle connection to the server: disconnect or reconnect"""
        if self.sock:
            try:
                self.sock.sendall(b'exit\n')
                self.sock.close()
            except:
                pass
            self.sock = None
            self.update_status("Disconnected", self.error_color)
            self.server_info_label.config(text="Server: Not connected")
            self.send_btn.config(state='disabled')
            self.entry.config(state='disabled')
            self.conn_btn.config(text="Connect")
            self.status_dot.itemconfig(1, fill=self.error_color)
        else:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.host, self.port))
                self.update_status("Connected", self.success_color)
                self.server_info_label.config(text=f"Server: {self.host}:{self.port}")
                self.send_btn.config(state='normal')
                self.entry.config(state='normal')
                self.conn_btn.config(text="Disconnect")
                self.status_dot.itemconfig(1, fill=self.success_color)
                
                # Welcome message
                self.clear_output()
                self.display_output(f"Connected to {self.host}:{self.port}\n", "success")
                self.display_output("Type commands and press Enter to execute.\n\n")
                
                # Focus on entry
                self.entry.focus_set()
                
            except Exception as e:
                messagebox.showerror("Connection Error", f"Could not connect to server: {e}")
                self.update_status("Error", self.error_color)
                
    def update_status(self, text, color):
        """Update status label with text and color"""
        self.status_label.config(text=text, fg=color)

    def clear_history(self):
        """Clear command history"""
        self.cmd_history.clear()
        self.history_listbox.delete(0, tk.END)

    def toggle_theme(self):
        """Toggle between light and dark theme"""
        if self.theme_mode == "dark":
            # Switch to light theme
            self.theme_mode = "light"
            self.bg_color = "#f5f5f5"
            self.text_bg = "#ffffff"
            self.text_fg = "#333333"
            self.button_bg = "#e0e0e0"
            self.button_fg = "#333333"
        else:
            # Switch to dark theme
            self.theme_mode = "dark"
            self.bg_color = "#1e1e1e"
            self.text_bg = "#2d2d2d"
            self.text_fg = "#f0f0f0"
            self.button_bg = "#3c3c3c"
            self.button_fg = "#f0f0f0"
            
        # Update all UI elements with new colors
        self.root.configure(bg=self.bg_color)
        
        # Update all frames with the new background color
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Frame):
                widget.configure(bg=self.bg_color)
                for child in widget.winfo_children():
                    if isinstance(child, tk.Frame):
                        child.configure(bg=self.bg_color)
                    elif isinstance(child, tk.Label) and child != self.path_label:
                        child.configure(bg=self.bg_color, fg=self.text_fg)
                    elif isinstance(child, tk.Button) and child != self.send_btn:
                        child.configure(bg=self.button_bg, fg=self.button_fg)
        
        # Update text area
        self.text_area.configure(bg=self.text_bg, fg=self.text_fg)
        
        # Update entry
        self.entry.configure(bg=self.text_bg, fg=self.text_fg)
        
        # Update history listbox
        self.history_listbox.configure(bg=self.text_bg, fg=self.text_fg)
        
        # Update theme button text
        self.theme_btn.config(text="Dark Theme" if self.theme_mode == "light" else "Light Theme")

    def create_server_config_dialog(self):
        """Create a dialog to configure server connection settings"""
        config_dialog = tk.Toplevel(self.root)
        config_dialog.title("Server Configuration")
        config_dialog.geometry("300x200")
        config_dialog.resizable(False, False)
        config_dialog.configure(bg=self.bg_color)
        config_dialog.transient(self.root)  # Set as transient to main window
        config_dialog.grab_set()  # Make it modal
        
        # Ensure dialog appears centered on parent window
        x = self.root.winfo_x() + (self.root.winfo_width() - 300) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 200) // 2
        config_dialog.geometry(f"+{x}+{y}")
        
        # Create form
        form_frame = tk.Frame(config_dialog, bg=self.bg_color, padx=20, pady=20)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Host field
        tk.Label(form_frame, text="Host:", bg=self.bg_color, fg=self.text_fg, 
                font=("Consolas", 10)).grid(row=0, column=0, sticky="w", pady=5)
        host_var = tk.StringVar(value=self.host)
        host_entry = tk.Entry(form_frame, textvariable=host_var, bg=self.text_bg, 
                            fg=self.text_fg, insertbackground=self.text_fg, width=20)
        host_entry.grid(row=0, column=1, sticky="ew", pady=5)
        
        # Port field
        tk.Label(form_frame, text="Port:", bg=self.bg_color, fg=self.text_fg,
                font=("Consolas", 10)).grid(row=1, column=0, sticky="w", pady=5)
        port_var = tk.StringVar(value=str(self.port))
        port_entry = tk.Entry(form_frame, textvariable=port_var, bg=self.text_bg,
                            fg=self.text_fg, insertbackground=self.text_fg, width=20)
        port_entry.grid(row=1, column=1, sticky="ew", pady=5)
        
        # Connection status
        status_text = "Connected" if self.sock else "Disconnected"
        status_color = self.success_color if self.sock else self.error_color
        tk.Label(form_frame, text=f"Status: {status_text}", bg=self.bg_color, 
                fg=status_color, font=("Consolas", 10, "bold")).grid(row=2, column=0, 
                columnspan=2, sticky="w", pady=10)
        
        # Buttons
        buttons_frame = tk.Frame(form_frame, bg=self.bg_color)
        buttons_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        def save_config():
            try:
                new_host = host_var.get()
                new_port = int(port_var.get())
                
                # Validate port
                if new_port < 1 or new_port > 65535:
                    messagebox.showerror("Invalid Port", "Port must be between 1 and 65535")
                    return
                    
                # Save new configuration
                self.host = new_host
                self.port = new_port
                
                # If currently connected, reconnect with new settings
                if self.sock:
                    messagebox.showinfo("Configuration Changed", 
                                      "Server configuration changed. Please reconnect to apply changes.")
                    self.toggle_connection()  # Disconnect
                
                config_dialog.destroy()
                
            except ValueError:
                messagebox.showerror("Invalid Input", "Port must be a number")
        
        save_btn = tk.Button(buttons_frame, text="Save", bg=self.accent_color, fg="white",
                           font=("Consolas", 9, "bold"), width=10, relief=tk.FLAT, command=save_config)
        save_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(buttons_frame, text="Cancel", bg=self.button_bg, fg=self.button_fg,
                              font=("Consolas", 9), width=10, relief=tk.FLAT, 
                              command=config_dialog.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Focus host entry
        host_entry.focus_set()

    def open_file_browser(self):
        """Open file browser dialog at current path"""
        if not self.sock:
            messagebox.showerror("Error", "Not connected to server")
            return
            
        # Refresh the file browser to ensure we have current data
        self.refresh_file_browser()
        
    def refresh_file_browser(self):
        """Refresh file browser with current directory content"""
        if not self.sock:
            return
            
        # Clear existing tree items
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
            
        # Get directory listing from current path
        # For Windows, use dir command with formatted output
        if platform.system().lower() == "windows":
            cmd = f'dir /a /-c "{self.current_path}"'
        else:
            # For Unix, use ls with details
            cmd = f'ls -la "{self.current_path}"'
            
        # Send command but process output locally
        threading.Thread(target=self.get_file_listing, args=(cmd,), daemon=True).start()
        
    def get_file_listing(self, cmd):
        """Get file listing from server and parse it into the tree view"""
        try:
            # Send command with newline
            self.sock.sendall((cmd + '\n').encode())
            
            # Get response
            raw_len = self.recvall(4)
            if not raw_len:
                return
                
            length = struct.unpack('>I', raw_len)[0]
            data = self.recvall(length)
            output = data.decode(errors='replace')
            
            # Process output based on system
            if platform.system().lower() == "windows":
                # Windows dir output parsing
                lines = output.split('\n')
                
                # Skip header/footer lines
                content_lines = []
                processing = False
                for line in lines:
                    if "Directory of" in line:
                        processing = True
                        continue
                    if processing and not line.strip():
                        processing = False
                    if processing and line.strip():
                        if not line.startswith(" "):  # Skip summary lines
                            content_lines.append(line)
                
                # Parse each line
                for line in content_lines:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        # Extract date and time
                        try:
                            date_str = " ".join(parts[0:3])
                            
                            # Determine if directory or file
                            if "<DIR>" in line:
                                # It's a directory
                                name_start = line.find("<DIR>") + 5
                                name = line[name_start:].strip()
                                self.file_tree.insert("", "end", text=name, values=("Directory", date_str), tags=("dir",))
                            else:
                                # It's a file, get size
                                size_str = parts[3].strip()
                                # Name is everything after the size
                                name_start = line.find(size_str) + len(size_str)
                                name = line[name_start:].strip()
                                
                                # Format size nicely
                                try:
                                    size_val = int(size_str.replace(',', ''))
                                    if size_val < 1024:
                                        formatted_size = f"{size_val} B"
                                    elif size_val < 1024*1024:
                                        formatted_size = f"{size_val/1024:.1f} KB"
                                    else:
                                        formatted_size = f"{size_val/(1024*1024):.1f} MB"
                                except:
                                    formatted_size = size_str
                                    
                                self.file_tree.insert("", "end", text=name, values=(formatted_size, date_str), tags=("file",))
                        except Exception as e:
                            # Skip lines we can't parse
                            continue
            else:
                # Unix ls output parsing (simpler layout)
                lines = output.split('\n')
                
                # Skip first line (total count) and process the rest
                for line in lines[1:]:
                    if not line.strip():
                        continue
                        
                    parts = line.split()
                    if len(parts) >= 9:
                        # Extract permissions, size, date and name
                        perms = parts[0]
                        size_str = parts[4]
                        date_str = " ".join(parts[5:8])
                        name = " ".join(parts[8:])
                        
                        # Skip . and .. entries
                        if name in [".", ".."]:
                            continue
                            
                        # Check if directory based on permissions
                        is_dir = perms.startswith('d')
                        
                        # Format size nicely
                        try:
                            size_val = int(size_str)
                            if size_val < 1024:
                                formatted_size = f"{size_val} B"
                            elif size_val < 1024*1024:
                                formatted_size = f"{size_val/1024:.1f} KB"
                            else:
                                formatted_size = f"{size_val/(1024*1024):.1f} MB"
                        except:
                            formatted_size = size_str
                            
                        if is_dir:
                            self.file_tree.insert("", "end", text=name, values=("Directory", date_str), tags=("dir",))
                        else:
                            self.file_tree.insert("", "end", text=name, values=(formatted_size, date_str), tags=("file",))
                            
            # Add visual styling to tree
            self.file_tree.tag_configure('dir', foreground='#569CD6')  # Blue for directories
            
        except Exception as e:
            # Show error in status bar
            self.update_status(f"Error listing files: {str(e)}", self.error_color)
            
    def file_browser_action(self, event):
        """Handle double click on file browser item"""
        item_id = self.file_tree.selection()[0]
        item_text = self.file_tree.item(item_id, "text")
        item_type = self.file_tree.item(item_id, "values")[0]
        
        if item_type == "Directory":
            # Change directory
            cmd = f"cd {item_text}"
            self.entry.delete(0, tk.END)
            self.entry.insert(0, cmd)
            self.send_command()
            # Refresh browser after directory change
            self.root.after(1000, self.refresh_file_browser)
        else:
            # For files, could add actions like view, download, etc.
            # For now just put the file name in the command entry
            self.entry.delete(0, tk.END)
            self.entry.insert(0, f"type {item_text}" if platform.system().lower() == "windows" else f"cat {item_text}")
            # Don't auto-execute for files, let the user decide

    def select_log_file(self):
        """Select a file for session logging"""
        path = fd.asksaveasfilename(
            defaultextension='.log', 
            filetypes=[('Log File', '*.log'), ('Text', '*.txt'), ('All Files', '*.*')],
            title="Select Session Log File"
        )
        if path:
            self.log_file = path
            if self.logging_enabled:
                self.start_logging()
                
    def toggle_logging(self):
        """Toggle session logging on/off"""
        self.logging_enabled = self.logging_var.get()
        
        if self.logging_enabled:
            # If we have a file path, start logging
            if self.log_file:
                self.start_logging()
            else:
                # Prompt for log file
                self.select_log_file()
        else:
            # Stop logging
            self.display_output("Session logging stopped.\n", "timestamp")
            
    def start_logging(self):
        """Start session logging"""
        if not self.log_file:
            return
            
        try:
            # Write header to log file
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n\n--- Session started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n")
                
            self.display_output(f"Session logging started. Log file: {self.log_file}\n", "timestamp")
        except Exception as e:
            messagebox.showerror("Logging Error", f"Could not start logging: {e}")
            self.logging_var.set(False)
            self.logging_enabled = False
            
    def log_to_file(self, text, is_command=False):
        """Write to log file if logging is enabled"""
        if not self.logging_enabled or not self.log_file:
            return
            
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime("%H:%M:%S")
                if is_command:
                    f.write(f"[{timestamp}] > {text}\n")
                else:
                    f.write(f"{text}")
        except Exception as e:
            # Disable logging if error occurs
            print(f"Logging error: {e}")
            self.logging_enabled = False
            self.logging_var.set(False)

if __name__ == '__main__':
    RemoteClient()