import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

load_dotenv()

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

def prepare_key(key_str: str) -> bytes:
    """
    문자열 형태의 키를 AESGCM에 사용 가능한 바이트 형태로 변환합니다.
    키 길이가 적절하지 않은 경우 PBKDF2를 사용하여 128비트 키로 변환합니다.
    
    매개변수:
        key_str (str): 환경 변수에서 가져온 문자열 형태의 키
        
    반환:
        bytes: AESGCM에 사용 가능한 바이트 형태의 키
    """
    # 문자열을 바이트로 변환
    if isinstance(key_str, str):
        try:
            # 16진수 문자열로 저장된 경우
            key = bytes.fromhex(key_str)
        except ValueError:
            # 일반 문자열인 경우 UTF-8로 인코딩
            key = key_str.encode('utf-8')
    else:
        key = key_str
    
    # AESGCM 키는 128, 192, 또는 256비트(16, 24, 또는 32바이트)여야 함
    if len(key) not in (16, 24, 32):  # 128, 192, 256 비트
        # 키 길이가 적절하지 않으면 PBKDF2를 사용하여 16바이트(128비트) 키로 변환
        salt = b'serendipity_salt'  # 실제 서비스에서는 안전한 salt 사용
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=16,  # 128 비트 키 생성
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(key)
    
    return key

def generate_key() -> bytes:
    """
    128비트(16바이트) 키를 생성합니다.
    속도와 보안을 고려하여 128비트 이상의 키 사용도 가능하지만, 메모리와 연산 효율을 고려해야 합니다.
    """
    return AESGCM.generate_key(bit_length=128)

def encrypt_chunk(chunk: str, key_str: str = None) -> bytes:
    """
    문자열로 된 문서 청크를 AES-GCM 방식으로 암호화합니다.
    
    매개변수:
        chunk (str): 암호화할 문서 청크.
        key_str (str, optional): 암호화에 사용할 키. 기본값은 None이며, 이 경우 환경 변수에서 키를 가져옵니다.
        
    반환:
        bytes: 암호문 (nonce + 암호화된 데이터).
    """
    # 키가 제공되지 않은 경우 환경 변수에서 가져옴
    if key_str is None:
        key_str = ENCRYPTION_KEY
    
    # 키 준비
    key = prepare_key(key_str)
    
    # 암호화
    aesgcm = AESGCM(key)
    # AES-GCM은 12바이트 길이의 nonce를 권장합니다.
    nonce = os.urandom(12)
    # associated_data는 None으로 설정합니다. 필요한 경우 추가적인 인증 데이터를 넣을 수 있습니다.
    encrypted_data = aesgcm.encrypt(nonce, chunk.encode('utf-8'), None)
    # nonce와 암호문을 함께 반환하여 복호화 시 nonce를 사용할 수 있도록 합니다.
    return nonce + encrypted_data

def decrypt_chunk(encrypted_chunk: bytes, key_str: str = None) -> str:
    """
    암호화된 청크를 복호화하여 원본 문자열로 반환합니다.
    
    매개변수:
        encrypted_chunk (bytes): nonce와 암호문이 결합된 데이터.
        key_str (str, optional): 암호화에 사용한 키. 기본값은 None이며, 이 경우 환경 변수에서 키를 가져옵니다.
        
    반환:
        str: 복호화된 문서 청크.
    """
    # 키가 제공되지 않은 경우 환경 변수에서 가져옴
    if key_str is None:
        key_str = ENCRYPTION_KEY
    
    # 키 준비
    key = prepare_key(key_str)
    
    # 복호화
    aesgcm = AESGCM(key)
    # 처음 12바이트는 nonce입니다.
    nonce = encrypted_chunk[:12]
    ct = encrypted_chunk[12:]
    decrypted_data = aesgcm.decrypt(nonce, ct, None)
    return decrypted_data.decode('utf-8')


# 예시 실행 코드 (테스트용)
if __name__ == "__main__":
    # 테스트 데이터
    test_data = "이것은 벡터 스토어에 저장될 문서 청크 예시입니다."
    print(f"원본 데이터: {test_data}")
    
    # 암호화
    encrypted = encrypt_chunk(test_data)
    print(f"암호화된 데이터 길이: {len(encrypted)} 바이트")
    
    # 복호화
    decrypted = decrypt_chunk(encrypted)
    print(f"복호화된 데이터: {decrypted}")
    
    # 원본 데이터와 복호화된 데이터가 일치하는지 확인
    if test_data == decrypted:
        print("암호화/복호화 성공: 원본 데이터와 복호화된 데이터가 일치합니다.")
    else:
        print("암호화/복호화 실패: 원본 데이터와 복호화된 데이터가 일치하지 않습니다.")
