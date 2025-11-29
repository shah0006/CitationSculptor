#!/usr/bin/env python3
"""
CitationSculptor GUI - Streamlit-based graphical interface.

Run with:
    streamlit run gui.py

Or use the launcher:
    python gui.py
"""

import streamlit as st
import subprocess
import sys
import os
from pathlib import Path
import time
import threading

# Add the project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def open_native_file_dialog() -> str:
    """Open native macOS/Windows/Linux file dialog and return selected file path."""
    import tkinter as tk
    from tkinter import filedialog
    
    # Create hidden root window
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)  # Bring dialog to front
    
    # Open file dialog
    file_path = filedialog.askopenfilename(
        title="Select Markdown File",
        filetypes=[
            ("Markdown files", "*.md"),
            ("Text files", "*.txt"),
            ("All files", "*.*")
        ]
    )
    
    root.destroy()
    return file_path if file_path else ""


def check_streamlit():
    """Check if streamlit is installed."""
    try:
        import streamlit
        return True
    except ImportError:
        return False


def launch_streamlit():
    """Launch this script with streamlit."""
    subprocess.run([sys.executable, "-m", "streamlit", "run", __file__, "--server.headless", "true"])


# If run directly (not through streamlit), launch streamlit
if __name__ == "__main__" and "streamlit" not in sys.modules:
    if not check_streamlit():
        print("Installing Streamlit...")
        subprocess.run([sys.executable, "-m", "pip", "install", "streamlit"])
    launch_streamlit()
    sys.exit(0)


# ============================================================================
# Streamlit App (runs when launched via streamlit)
# ============================================================================

from modules.file_handler import FileHandler
from modules.reference_parser import ReferenceParser
from modules.type_detector import CitationTypeDetector, CitationType
from modules.output_generator import CorrectionsHandler


def init_session_state():
    """Initialize session state variables."""
    defaults = {
        'processed': False,
        'output_content': None,
        'corrections_content': None,
        'stats': None,
        'input_file_path': None,
        'output_folder': None,
        'last_output_folder': None,
        'native_file_selected': False,
        'processing_log': [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def run_citation_sculptor(file_path: str, options: dict) -> dict:
    """Run CitationSculptor on the given file."""
    from citation_sculptor import CitationSculptor
    
    sculptor = CitationSculptor(
        input_path=file_path,
        output_path=options.get('output_path'),
        verbose=options.get('verbose', False),
        dry_run=options.get('dry_run', False),
        create_backup=options.get('create_backup', True),
        multi_section=options.get('multi_section', True),
    )
    
    success = sculptor.run()
    
    # Determine output path
    if sculptor.output_path:
        output_path = sculptor.output_path
    else:
        output_path = str(Path(file_path).parent / f"{Path(file_path).stem}_formatted.md")
    
    return {
        'success': success,
        'output_path': output_path,
        'processed_count': len(sculptor.processed_citations),
        'review_count': len(sculptor.manual_review_items),
        'mapping_count': len(sculptor.number_to_label_map),
    }


def main():
    """Main Streamlit application."""
    init_session_state()
    
    # Page config
    st.set_page_config(
        page_title="CitationSculptor",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
        <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #1E3A5F 0%, #4A90A4 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        .sub-header {
            font-size: 1.1rem;
            color: #6B7280;
            margin-bottom: 2rem;
        }
        .stMetric {
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
            padding: 1rem;
            border-radius: 0.75rem;
            border: 1px solid #e2e8f0;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown('<p class="main-header">📚 CitationSculptor</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Transform LLM-generated references into Vancouver-style citations</p>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Processing Options")
        
        multi_section = st.checkbox(
            "Multi-section mode",
            value=True,
            help="Process documents with multiple independent reference sections"
        )
        
        create_backup = st.checkbox(
            "Create backup",
            value=True,
            help="Create a backup of the original file before processing"
        )
        
        dry_run = st.checkbox(
            "Dry run (preview only)",
            value=False,
            help="Preview changes without writing output files"
        )
        
        verbose = st.checkbox(
            "Verbose logging",
            value=False,
            help="Show detailed processing logs"
        )
        
        st.divider()
        
        st.header("ℹ️ About")
        st.markdown("""
        **CitationSculptor** processes markdown documents 
        with LLM-generated reference sections and reformats 
        them to Vancouver citation standards.
        
        **Supported types:**
        - 📄 Journal articles (PubMed)
        - 📕 Book chapters (CrossRef)
        - 🌐 Webpages & blogs
        - 📰 Newspaper articles
        """)
        
        st.divider()
        
        # Server status
        st.header("🔌 Server Status")
        try:
            from modules.pubmed_client import PubMedClient
            client = PubMedClient()
            if client.test_connection():
                st.success("✅ PubMed MCP Server connected")
            else:
                st.error("❌ Server not responding")
        except Exception as e:
            st.error(f"❌ Error: {str(e)[:40]}")
    
    # Main content - Tabs
    tab1, tab2, tab3 = st.tabs(["📄 Process Document", "🔧 Apply Corrections", "📊 Results"])
    
    # ========== TAB 1: Process Document ==========
    with tab1:
        st.header("Select & Process Document")
        
        # Input method selection
        input_method = st.radio(
            "Choose input method:",
            ["📁 Enter file path", "📤 Upload file", "📂 Browse test samples"],
            horizontal=True
        )
        
        file_path = None
        file_content = None
        
        if input_method == "📁 Enter file path":
            col1, col2 = st.columns([4, 1])
            
            with col1:
                # Direct file path input
                default_path = st.session_state.get('input_file_path', "")
                file_path_input = st.text_input(
                    "File path:",
                    value=default_path,
                    placeholder="/Users/you/Documents/your_document.md",
                    help="Enter the full path to any markdown file on your computer",
                    key="file_path_text"
                )
            
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("📂 Browse...", help="Open native file browser"):
                    try:
                        selected_path = open_native_file_dialog()
                        if selected_path:
                            st.session_state.input_file_path = selected_path
                            st.rerun()
                    except Exception as e:
                        st.error(f"Could not open file browser: {e}")
            
            # Use session state path if text input is empty but we have a stored path
            if not file_path_input and st.session_state.get('input_file_path'):
                file_path_input = st.session_state.input_file_path
            
            if file_path_input:
                path = Path(file_path_input)
                if path.exists():
                    file_path = str(path)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    st.session_state.input_file_path = file_path
                    st.success(f"✅ File loaded: {path.name} ({len(file_content):,} characters)")
                    st.caption(f"📁 Output will be saved to: `{path.parent}`")
                else:
                    st.error(f"❌ File not found: {file_path_input}")
        
        elif input_method == "📤 Upload file":
            st.info("💡 **Recommended:** Use the native file browser to select your file. Output will be saved to the same folder.")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown("Click the button to open your system's file browser →")
            with col2:
                if st.button("📂 Select File...", type="primary", use_container_width=True):
                    try:
                        selected_path = open_native_file_dialog()
                        if selected_path:
                            st.session_state.input_file_path = selected_path
                            st.session_state.native_file_selected = True
                            st.rerun()
                    except Exception as e:
                        st.error(f"Could not open file browser: {e}")
            
            # Show selected file info
            if st.session_state.get('native_file_selected') and st.session_state.get('input_file_path'):
                selected = Path(st.session_state.input_file_path)
                if selected.exists():
                    file_path = str(selected)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    st.success(f"✅ Selected: **{selected.name}** ({len(file_content):,} characters)")
                    st.caption(f"📁 Output will be saved to: `{selected.parent}`")
            
            st.divider()
            st.caption("Or drag & drop a file (output folder must be specified manually):")
            
            # Fallback: traditional uploader
            uploaded_file = st.file_uploader(
                "Drop file here:",
                type=['md', 'markdown', 'txt'],
                help="Fallback option - you'll need to specify output folder",
                label_visibility="collapsed"
            )
            
            if uploaded_file and not st.session_state.get('native_file_selected'):
                # Output folder for drag-drop uploads
                default_folder = st.session_state.get('last_output_folder', str(Path.home() / "Documents"))
                output_folder = st.text_input(
                    "Save output to:",
                    value=default_folder,
                    help="Where to save the formatted output"
                )
                
                file_content = uploaded_file.getvalue().decode('utf-8')
                
                if output_folder and Path(output_folder).exists():
                    save_path = Path(output_folder) / uploaded_file.name
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(file_content)
                    file_path = str(save_path)
                    st.session_state.input_file_path = file_path
                    st.session_state.last_output_folder = output_folder
                    st.success(f"✅ File saved to: `{save_path}`")
                elif output_folder:
                    st.error(f"❌ Folder not found: {output_folder}")
        
        else:  # Browse test samples
            # List files from test_samples and samples directories
            test_dir = Path(__file__).parent / "test_samples"
            samples_dir = Path(__file__).parent / "samples"
            
            available_files = []
            if test_dir.exists():
                available_files.extend(list(test_dir.glob("*.md")))
            if samples_dir.exists():
                available_files.extend(list(samples_dir.glob("*.md")))
            
            if available_files:
                selected = st.selectbox(
                    "Select a file:",
                    sorted(available_files, key=lambda x: x.name),
                    format_func=lambda x: f"{x.parent.name}/{x.name}"
                )
                if selected:
                    file_path = str(selected)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    st.session_state.input_file_path = file_path
                    st.success(f"✅ Selected: {selected.name} ({len(file_content):,} characters)")
            else:
                st.warning("No markdown files found in test_samples/ or samples/")
        
        # Show file preview
        if file_content:
            with st.expander("📝 File Preview", expanded=False):
                st.code(file_content[:3000] + ("\n..." if len(file_content) > 3000 else ""), language="markdown")
            
            # Show detected sections
            try:
                parser = ReferenceParser(file_content, multi_section=True)
                sections = parser.parse_multi_section()
                
                if sections:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Reference Sections", len(sections))
                    with col2:
                        total_refs = sum(len(s.references) for s in sections)
                        st.metric("Total References", total_refs)
                    with col3:
                        st.metric("Inline Style", sections[0].inline_ref_style if sections else "N/A")
            except Exception as e:
                st.warning(f"Could not parse sections: {e}")
        
        # Process button
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            process_btn = st.button(
                "🚀 Process Document", 
                type="primary", 
                use_container_width=True, 
                disabled=not file_path
            )
        
        if process_btn:
            with st.spinner("Processing citations... This may take a minute."):
                progress_bar = st.progress(0, text="Initializing...")
                
                try:
                    options = {
                        'multi_section': multi_section,
                        'create_backup': create_backup,
                        'dry_run': dry_run,
                        'verbose': verbose,
                    }
                    
                    progress_bar.progress(20, text="Connecting to PubMed...")
                    result = run_citation_sculptor(file_path, options)
                    progress_bar.progress(80, text="Finalizing...")
                    
                    if result['success']:
                        st.session_state.processed = True
                        st.session_state.stats = result
                        
                        # Read output content
                        if not dry_run and Path(result['output_path']).exists():
                            with open(result['output_path'], 'r', encoding='utf-8') as f:
                                st.session_state.output_content = f.read()
                            
                            # Check for Null citations and generate corrections
                            if 'Null_' in st.session_state.output_content:
                                handler = CorrectionsHandler()
                                corrections_path = handler.generate_corrections_template(
                                    st.session_state.output_content,
                                    result['output_path']
                                )
                                if corrections_path and Path(corrections_path).exists():
                                    with open(corrections_path, 'r', encoding='utf-8') as f:
                                        st.session_state.corrections_content = f.read()
                        
                        progress_bar.progress(100, text="Complete!")
                        st.success("✅ Processing complete! Check the **Results** tab.")
                        st.balloons()
                    else:
                        progress_bar.progress(100, text="Failed")
                        st.error("❌ Processing failed. Check logs for details.")
                
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    if verbose:
                        st.exception(e)
    
    # ========== TAB 2: Apply Corrections ==========
    with tab2:
        st.header("Fix Incomplete Citations")
        
        st.markdown("""
        When websites block automated scraping, citations may have `Null_Date` or `Null_Author` 
        placeholders. Use this tool to manually fix them.
        """)
        
        if st.session_state.corrections_content:
            st.success(f"📋 A corrections template was generated with incomplete citations.")
            
            # Editable corrections
            edited_corrections = st.text_area(
                "Edit Corrections Template:",
                st.session_state.corrections_content,
                height=400,
                help="Fill in the missing information (Date, Authors, etc.) then click Apply"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Apply Corrections", type="primary", use_container_width=True):
                    with st.spinner("Applying corrections..."):
                        try:
                            handler = CorrectionsHandler()
                            
                            # Save edited corrections to temp file
                            temp_path = Path("/tmp/corrections_temp.md")
                            with open(temp_path, 'w', encoding='utf-8') as f:
                                f.write(edited_corrections)
                            
                            corrections = handler.parse_corrections_file(str(temp_path))
                            
                            if corrections and st.session_state.output_content:
                                updated_content, count = handler.apply_corrections(
                                    st.session_state.output_content,
                                    corrections
                                )
                                
                                st.session_state.output_content = updated_content
                                
                                # Write back to file
                                if st.session_state.stats and 'output_path' in st.session_state.stats:
                                    with open(st.session_state.stats['output_path'], 'w', encoding='utf-8') as f:
                                        f.write(updated_content)
                                
                                st.success(f"✅ Applied {count} correction(s)!")
                                st.rerun()
                            else:
                                st.warning("No corrections to apply. Fill in the fields first.")
                        
                        except Exception as e:
                            st.error(f"Error: {e}")
            
            with col2:
                if st.button("🔄 Refresh Template", use_container_width=True):
                    if st.session_state.output_content:
                        handler = CorrectionsHandler()
                        null_citations = handler._find_null_citations(st.session_state.output_content)
                        if null_citations:
                            st.session_state.corrections_content = handler._build_template(null_citations)
                            st.rerun()
                        else:
                            st.success("No more corrections needed!")
                            st.session_state.corrections_content = None
        
        else:
            st.info("👆 Process a document first. If it has missing data, a corrections template will appear here.")
            
            st.divider()
            
            # Manual file upload option
            st.subheader("Or load files manually:")
            
            col1, col2 = st.columns(2)
            with col1:
                corrections_path = st.text_input("Corrections file path:", placeholder="path/to/corrections.md")
            with col2:
                formatted_path = st.text_input("Formatted document path:", placeholder="path/to/document_formatted.md")
            
            if corrections_path and formatted_path:
                if st.button("Apply Corrections from Files"):
                    try:
                        handler = CorrectionsHandler()
                        output_path, count = handler.apply_corrections_to_file(formatted_path, corrections_path)
                        st.success(f"✅ Applied {count} corrections to {output_path}")
                    except Exception as e:
                        st.error(f"Error: {e}")
    
    # ========== TAB 3: Results ==========
    with tab3:
        st.header("Processing Results")
        
        if st.session_state.processed and st.session_state.stats:
            stats = st.session_state.stats
            
            # Stats metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Citations Processed", stats.get('processed_count', 0))
            with col2:
                st.metric("Inline Refs Updated", stats.get('mapping_count', 0))
            with col3:
                st.metric("Manual Review", stats.get('review_count', 0))
            with col4:
                null_count = st.session_state.output_content.count('Null_') if st.session_state.output_content else 0
                st.metric("Incomplete", null_count)
            
            st.divider()
            
            # Output file info
            if 'output_path' in stats:
                st.success(f"📄 **Output saved to:** `{stats['output_path']}`")
            
            # Warnings
            if st.session_state.output_content:
                null_count = st.session_state.output_content.count('Null_')
                if null_count > 0:
                    st.warning(f"⚠️ **{null_count} citation(s)** have missing information. Go to the **Apply Corrections** tab to fix them.")
            
            # Document preview
            if st.session_state.output_content:
                with st.expander("📝 Formatted Document Preview", expanded=False):
                    # Show references section
                    content = st.session_state.output_content
                    ref_start = content.find("## References")
                    if ref_start > 0:
                        st.code(content[ref_start:ref_start+3000], language="markdown")
                    else:
                        st.code(content[-3000:], language="markdown")
                
                # Download button
                st.download_button(
                    "📥 Download Formatted Document",
                    st.session_state.output_content,
                    file_name=Path(stats.get('output_path', 'document_formatted.md')).name,
                    mime="text/markdown",
                    use_container_width=True
                )
        
        else:
            st.info("📤 Process a document to see results here.")
            
            # Show example
            with st.expander("📖 Example Output"):
                st.markdown("""
                ```markdown
                ## References
                
                [^SmithJ-2024-12345678]: Smith J, Jones A, Brown B. 
                Article Title. Journal Name. 2024;15(3):123-130. 
                [DOI](https://doi.org/10.1234/example). 
                [PMID: 12345678](https://pubmed.ncbi.nlm.nih.gov/12345678/)
                
                [^WHO-GlobalHealth-2023]: World Health Organization (WHO). 
                Global Health Report. 2023. 
                [Link](https://www.who.int/reports/global-health-2023)
                ```
                """)


if __name__ == "__main__":
    main()

