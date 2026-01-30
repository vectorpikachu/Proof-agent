import os, shutil, signal, sys, tempfile, atexit
from env import coqstoq_root, _coqstoq_root, bak_coqstoq_root

class FileRestorer:
    def __init__(self):
        self.backups = {}
        self._original_handlers = {}
    
    def backup(self, filepath):
        """Create a backup of a file before modifying it"""
        if filepath not in self.backups and os.path.exists(filepath):
            # Create backup in a temporary location
            backup_file = tempfile.NamedTemporaryFile(delete=False)
            backup_file.close()
            shutil.copy2(filepath, backup_file.name)
            self.backups[filepath] = backup_file.name
    
    def _signal_handler(self, sig, frame):
        """Handle termination signals"""
        print(f"\nCaught signal {sig}, restoring files...")
        self._restore_all()
        
        # Call original handler if it exists
        if sig in self._original_handlers and self._original_handlers[sig]:
            self._original_handlers[sig](sig, frame)
        sys.exit(1)
    
    def _restore_all(self):
        """Restore all backed up files"""
        for original_path, backup_path in self.backups.items():
            if os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, original_path)
                    os.remove(backup_path)
                except Exception as e:
                    print(f"Error restoring {original_path}: {e}")
                finally:
                    print(f"Restored {original_path}")
        self.backups.clear()

    
    def __enter__(self):
        # Register signal handlers
        signals = [signal.SIGINT, signal.SIGTERM]
        for sig in signals:
            self._original_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, self._signal_handler)
        
        # Register for normal exit
        atexit.register(self._restore_all)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore files on exception
        self._restore_all()
        
        # Restore original signal handlers
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)
        
        return False  # Allow exceptions to propagate