#!/usr/bin/env python3
"""
Password Dialog for Ruuf USB Flasher
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit

class PasswordDialog(QDialog):
    """
    Dialog for getting sudo password on Linux
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Authentication Required")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Message
        message = QLabel("This operation requires administrative privileges.\nPlease enter your password:")
        layout.addWidget(message)
        
        # Password field
        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_field)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def get_password(self):
        """Return the entered password"""
        return self.password_field.text()