from prepare_easyocr import prepare_easyocr
from prepare_kiwipiepy import prepare_kiwipiepy

if __name__ == "__main__":
    print("Preparing EasyOCR models...")
    prepare_easyocr()
    
    print("Preparing Kiwipiepy models...")
    prepare_kiwipiepy()
    
    print("Model preparation completed!")
