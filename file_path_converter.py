import re

# 특수 문자와 실제 문자 간의 매핑
char_mapping = {
    '\\': '[[BACKSLASH]]',
    '/': '[[SLASH]]',
    ':': '[[COLON]]',
    '*': '[[ASTERISK]]',
    '?': '[[QUESTION]]',
    '"': '[[QUOTE]]',
    '<': '[[LESS]]',
    '>': '[[GREATER]]',
    '|': '[[PIPE]]',
    ' ': '[[SPACE]]',
    '.': '[[DOT]]',
    ',': '[[COMMA]]',
    ';': '[[SEMICOLON]]',
    '=': '[[EQUAL]]',
    '(': '[[LPAREN]]',
    ')': '[[RPAREN]]',
    # '[': '[[LBRACKET]]',
    # ']': '[[RBRACKET]]',
    '{': '[[LBRACE]]',
    '}': '[[RBRACE]]',
    '&': '[[AMPERSAND]]',
    '^': '[[CARET]]',
    '%': '[[PERCENT]]',
    '$': '[[DOLLAR]]',
    '#': '[[HASH]]',
    '@': '[[AT]]',
    '!': '[[EXCLAMATION]]',
    '`': '[[BACKTICK]]',
    '~': '[[TILDE]]',
    '+': '[[PLUS]]',
    #'-': '[[MINUS]]',
    #'_': '[[UNDERSCORE]]',
    "'": '[[SINGLEQUOTE]]'
}

# 드라이브 문자 매핑
drive_mapping = {
    'C:': '[[DRIVE_C]]',
    'D:': '[[DRIVE_D]]',
    'E:': '[[DRIVE_E]]',
    'F:': '[[DRIVE_F]]'
}

def path_to_filename(path):
    # 드라이브 문자 변환
    for drive, replacement in drive_mapping.items():
        if path.startswith(drive):
            path = path.replace(drive, replacement, 1)
            break
    
    # 나머지 경로의 특수 문자 변환
    for char, replacement in char_mapping.items():
        path = path.replace(char, replacement)
    
    # 경로 구분자를 [[PATH]]로 변환
    path = re.sub(r'(\[\[BACKSLASH\]\]|\[\[SLASH\]\])', '[[PATH]]', path)
    
    return path

def filename_to_path(filename):
    # 드라이브 문자 복원
    for drive, replacement in drive_mapping.items():
        if filename.startswith(replacement):
            filename = filename.replace(replacement, drive, 1)
            break
    
    # [[PATH]]를 경로 구분자로 복원
    filename = filename.replace('[[PATH]]', '\\')
    
    # 나머지 특수 문자 복원
    for char, replacement in char_mapping.items():
        filename = filename.replace(replacement, char)
    
    return filename


