from typing import List
from kiwipiepy import Kiwi
import re

kiwi = Kiwi()

def extract_simple_keywords(query: str) -> List[str]:
    """
    주어진 질의 문장에서 2글자 이상의 한글 단어와 영어 단어를 추출합니다.
    """
    english_keywords = re.findall(r'\b[A-Za-z]{2,}\b', query)
    korean_keywords = re.findall(r'[가-힣]{2,}', query)
    return english_keywords + korean_keywords

def extract_keywords(query: str) -> List[str]:
    """
    Kiwi 형태소 분석기와 정규식을 결합하여 키워드 추출
    """
    keywords = set()
    analyzed = kiwi.tokenize(query)
    
    not_keywords = {'NNG', 'NNP', 'NNB','NR','NP','V','VV','VA','VX','VCP','VCN','MM','MAG','MAJ',
                    'IC','J','JKS','JKC','JKG','JKO','JKB','JKV','JKQ','JX','JC','EP','EF','EC','ETN',
                    'ETM','SF','SP','SS','SE','SO','SW','SL','SH','SN','XPN','XSN','XSV','XSA','XR',
                    'W_EMOJI','VA-I'}
    
    # Kiwi 기반 추출
    for sentence in analyzed:
        for token in sentence:
            if not isinstance(token, str) or token in not_keywords or len(token) <=1:
                continue
            keywords.add(token)

    return list(keywords)

if __name__ == '__main__':
    import unittest

    class TestExtractKeywords(unittest.TestCase):
        def test_korean_nouns(self):
            query = "아버지의 성적은 어떻습니까?"
            result = extract_keywords(query)
            self.assertIn("아버지", result)
            self.assertIn("성적", result)

        def test_english_words(self):
            query = "The quick brown fox jumps over the lazy dog"
            result = extract_keywords(query)
            expected = ["The", "quick", "brown", "fox", "jumps", "over", "lazy", "dog"]
            for word in expected:
                self.assertIn(word, result)

        def test_mixed_language(self):
            query = "아버지와 어머니 and father and mother"
            result = extract_keywords(query)
            self.assertIn("아버지", result)
            self.assertIn("어머니", result)
            self.assertIn("father", result)
            self.assertIn("mother", result)

        def test_empty_input(self):
            query = ""
            result = extract_keywords(query)
            self.assertEqual(result, [])

        def test_fallback_regexp(self):
            query = "1234!@#한글 English"
            result = extract_keywords(query)
            self.assertIn("한글", result)
            self.assertIn("English", result)

    unittest.main()