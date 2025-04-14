import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
from bs4 import BeautifulSoup
import re
from spellchecker import SpellChecker

class SpellingCheckerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Spelling Checker Tool")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # Set up the spell checker
        self.spell = SpellChecker()
        
        # Create main frame
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = ttk.Label(main_frame, text="Spelling Checker", font=("Arial", 18, "bold"))
        title_label.pack(pady=10)
        
        # Input selection frame
        self.selection_frame = ttk.LabelFrame(main_frame, text="Select Input Type", padding="10")
        self.selection_frame.pack(fill=tk.X, pady=10)
        
        # Radio buttons for input selection
        self.input_type = tk.StringVar(value="text")
        
        text_radio = ttk.Radiobutton(
            self.selection_frame, 
            text="Check Text", 
            variable=self.input_type, 
            value="text",
            command=self.update_input_area
        )
        text_radio.grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        
        url_radio = ttk.Radiobutton(
            self.selection_frame, 
            text="Check Website Content", 
            variable=self.input_type, 
            value="url",
            command=self.update_input_area
        )
        url_radio.grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)
        
        # Input frame
        self.input_frame = ttk.LabelFrame(main_frame, text="Input", padding="10")
        self.input_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # URL entry (initially hidden)
        self.url_frame = ttk.Frame(self.input_frame)
        self.url_label = ttk.Label(self.url_frame, text="Enter Website URL:")
        self.url_label.pack(side=tk.LEFT, padx=5)
        self.url_entry = ttk.Entry(self.url_frame, width=50)
        self.url_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Text input area
        self.text_frame = ttk.Frame(self.input_frame)
        self.text_label = ttk.Label(self.text_frame, text="Enter Text:")
        self.text_label.pack(anchor=tk.W, padx=5, pady=5)
        self.text_input = scrolledtext.ScrolledText(self.text_frame, height=10)
        self.text_input.pack(fill=tk.BOTH, expand=True, padx=5)
        
        # Show the right input based on default selection
        self.update_input_area()
        
        # Check button
        self.check_button = ttk.Button(main_frame, text="Check Spelling", command=self.check_spelling)
        self.check_button.pack(pady=10)
        
        # Results frame
        self.results_frame = ttk.LabelFrame(main_frame, text="Spelling Errors", padding="10")
        self.results_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Results display
        self.results_text = scrolledtext.ScrolledText(self.results_frame, height=10)
        self.results_text.pack(fill=tk.BOTH, expand=True)
        self.results_text.config(state=tk.DISABLED)
    
    def update_input_area(self):
        # Hide all input frames first
        self.text_frame.pack_forget()
        self.url_frame.pack_forget()
        
        # Show the appropriate input area based on selection
        if self.input_type.get() == "text":
            self.text_frame.pack(fill=tk.BOTH, expand=True)
        else:  # url
            self.url_frame.pack(fill=tk.X, pady=10)
            self.text_frame.pack(fill=tk.BOTH, expand=True)
            self.text_label.config(text="Website Content (will be loaded after checking):")
            self.text_input.config(state=tk.DISABLED)
    
    def extract_text_from_url(self, url):
        try:
            # Add http:// if not present
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.extract()
            
            # Get text
            text = soup.get_text()
            
            # Clean up text - break into lines and remove leading/trailing space
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # Drop blank lines
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch content from URL: {str(e)}")
            return ""
    
    def check_spelling(self):
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        
        if self.input_type.get() == "url":
            url = self.url_entry.get().strip()
            if not url:
                messagebox.showwarning("Input Required", "Please enter a URL.")
                self.results_text.config(state=tk.DISABLED)
                return
                
            # Extract text from website
            text = self.extract_text_from_url(url)
            
            # Update the text area with the content
            self.text_input.config(state=tk.NORMAL)
            self.text_input.delete(1.0, tk.END)
            self.text_input.insert(tk.END, text[:10000] + ("..." if len(text) > 10000 else ""))
            self.text_input.config(state=tk.DISABLED)
        else:
            text = self.text_input.get(1.0, tk.END).strip()
            if not text:
                messagebox.showwarning("Input Required", "Please enter some text.")
                self.results_text.config(state=tk.DISABLED)
                return
        
        # Analyze text for spelling errors
        self.find_spelling_errors(text)
        
    def find_spelling_errors(self, text):
        # Clean the text and split into words
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        
        # Find misspelled words
        misspelled = self.spell.unknown(words)
        
        if not misspelled:
            self.results_text.insert(tk.END, "No spelling errors found!")
        else:
            self.results_text.insert(tk.END, f"Found {len(misspelled)} spelling errors:\n\n")
            
            for word in misspelled:
                corrections = self.spell.candidates(word)
                suggested = list(corrections)[:3]  # Get up to 3 suggestions
                
                suggestion_text = ', '.join(suggested) if suggested else "No suggestions"
                self.results_text.insert(tk.END, f"• '{word}' → Suggestions: {suggestion_text}\n")
        
        self.results_text.config(state=tk.DISABLED)

def main():
    root = tk.Tk()
    app = SpellingCheckerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()