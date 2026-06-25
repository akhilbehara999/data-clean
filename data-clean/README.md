<div align="center">

# 🧹 Data Sanitizer

### **Clean your data in seconds — not hours.**

Data Sanitizer is a production-grade data cleaning platform that diagnoses, transforms, and exports sanitized datasets through a guided, visual 4-step wizard. Powered by Streamlit and Pandas.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit 1.36+](https://img.shields.io/badge/Streamlit-1.36+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Pandas 2.0+](https://img.shields.io/badge/Pandas-2.0+-150458?style=for-the-badge&logo=pandas&logoColor=white)](https://pandas.pydata.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[🚀 Quick Start](#-quick-start) • [✨ Key Features](#-key-features) • [🩹 Supported Cleaning Operations](#-supported-cleaning-operations) • [🏗️ Architecture](#%EF%B8%8F-architecture)

</div>

---

## 🎯 What is Data Sanitizer?

Data Sanitizer is a **no-code data cleaning platform** built for analysts, engineers, and researchers to clean messy CSV and Excel files. 

Every transformation is transparent, previewable, and reversible. It computes cell-level differences and provides a complete audit trail of applied operations so you can trust your final export.

---

## ✨ Key Features

### 🔍 1. Smart Profiling & Diagnostics
- **Automated Type Inference**: Detects data types including text, numeric, date, boolean, and mixed columns.
- **Diagnostics Dashboard**: Instantly flags missing values, duplicate records, statistical outliers, and structural inconsistencies.
- **Dataset Health Score**: Computes a single quality percentage (0–100%) summarizing your dataset's integrity.

### 🩹 2. Interactive Cleaning Wizard
- **Issue-Based Cards**: Reviews recommended fixes grouped by severity, confidence, and type.
- **Staged Before/After Previews**: Sees exactly what data will change at a cell level before committing.
- **One-Click Corrections**: Toggle individual filters or execute all suggested fixes instantly.

### 📊 3. Transformation Explorer
- **Visual Diff Engine**: View original vs. cleaned cells side-by-side.
- **Impact Indicators**: View which columns underwent the most substantial changes.
- **Downloadable Changelog**: Export a complete history of executed operations for compliance and verification.

### 📦 4. Multi-Format Export Package
- Export cleaned datasets directly as **CSV** or **Excel**.
- Export a detailed **Diagnostics Report**.
- Download a comprehensive **ZIP package** containing the cleaned dataset, diagnostics report, and full changelog.

---

## 🩹 Supported Cleaning Operations

| Operation | Description | Confidence |
| :--- | :--- | :--- |
| 🩹 **Missing Values** | Impute nulls using Mean, Median, Mode, or custom placeholders | **High** |
| 👯 **Duplicates** | Deduplicate rows with options for specific subset columns | **High** |
| ✂️ **Whitespace** | Strip leading, trailing, and redundant consecutive spaces | **High** |
| 🔤 **Case Normalization** | Normalize text to UPPERCASE, lowercase, or Title Case | **High** |
| 📅 **Date Standardization** | Parse and normalize inconsistent date formats to ISO (YYYY-MM-DD) | **Medium** |
| 🔢 **Numeric Conversion** | Clean currency symbols, commas, and convert strings to numeric | **High** |
| 💡 **Boolean Normalization**| Convert Yes/No, True/False, 1/0 text variations into boolean flags | **High** |
| 🚫 **Special Characters** | Remove non-printable control characters and corrupted encodings | **Medium** |
| 🏷️ **Column Operations** | Rename, drop, split, or merge columns interactively | **High** |
| 📊 **Outlier Capping** | Identify and limit extreme values using IQR or Z-score thresholds | **Medium** |
| ⚠️ **Range Validation** | Impose constraints (e.g. `Age >= 0`) and flag violations | **Medium** |

---

## 🏗️ Architecture

```
data-clean/
├── core/               # Cleaning operations, diagnostics, and profiler logic
│   ├── cleaner.py      # Core data manipulation logic
│   ├── diagnostics.py  # Health scoring & column profiling
│   ├── loader.py       # Safe file ingestion (with encoding detection)
│   └── profiler.py     # Issues generation & diagnostics suite
├── ui/                 # UI components and shell structure
│   ├── components.py   # Step components, wizard cards & preview widgets
│   ├── shell.py        # Stepper control & page header
│   └── theme.py        # CSS styling overrides & design tokens
├── app.py              # Application entrypoint (Streamlit wizard)
├── requirements.txt    # Project dependencies
└── README.md           # Documentation (this file)
```

---

## 🚀 Quick Start

### 📋 Prerequisites
- **Python 3.10** or higher
- **pip** (Python package manager)

### ⚙️ Installation & Running

1. **Clone the Repository**
   ```bash
   git clone https://github.com/akhilbehara999/data-clean.git
   cd data-clean
   ```

2. **Set up a Virtual Environment (Recommended)**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the Application**
   ```bash
   streamlit run app.py
   ```

The application will start and open automatically in your default browser at **`http://localhost:8501`**.

---

<div align="center">

**Built with ❤️ using Streamlit & Pandas**

</div>
