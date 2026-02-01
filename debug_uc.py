
import sys
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
try:
    import undetected_chromedriver as uc
    print("✅ undetected_chromedriver imported successfully")
    print(f"File: {uc.__file__}")
except ImportError as e:
    print(f"❌ ImportError: {e}")
    import site
    print(f"sys.path: {sys.path}")
    print(f"site packages: {site.getsitepackages()}")
