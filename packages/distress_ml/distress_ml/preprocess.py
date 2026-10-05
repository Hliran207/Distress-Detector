import re
import nltk
from nltk.corpus import stopwords, wordnet
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

nltk.download("stopwords", quiet=True)
nltk.download("wordnet", quiet=True)
nltk.download("punkt", quiet=True)
nltk.download("averaged_perceptron_tagger", quiet=True)
nltk.download("omw-1.4", quiet=True)

lemmatizer = WordNetLemmatizer()

base_stopwords = set(stopwords.words("english"))
words_to_keep = {
    "feel",
    "feeling",
    "felt",
    "feels",
    "want",
    "wanted",
    "wants",
    "need",
    "needed",
    "needs",
    "help",
    "hope",
    "hopeless",
    "helpless",
    "alone",
    "empty",
    "pain",
    "hurt",
    "hurts",
    "happy",
    "sad",
    "angry",
    "scared",
    "afraid",
    "anxious",
    "tired",
    "exhausted",
    "lost",
    "broken",
    "numb",
    "better",
    "worse",
    "bad",
    "good",
    "not",
    "no",
    "never",
    "nor",
    "neither",
    "nothing",
    "nobody",
    "nowhere",
    "hardly",
    "barely",
    "scarcely",
}
FINAL_STOPWORDS = base_stopwords - words_to_keep


def get_wordnet_pos(treebank_tag):
    if treebank_tag.startswith("J"):
        return wordnet.ADJ
    if treebank_tag.startswith("V"):
        return wordnet.VERB
    if treebank_tag.startswith("N"):
        return wordnet.NOUN
    if treebank_tag.startswith("R"):
        return wordnet.ADV
    return wordnet.NOUN


def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r"http\S+|www\.\S+", "", text)
    text = re.sub(r"r/\w+", "", text)
    text = re.sub(r"u/\w+", "", text)
    text = re.sub(r"&amp;|&lt;|&gt;|&quot;|&apos;", "", text)
    text = re.sub(r"\*{1,}|#{1,}|>{1,}|_{2,}|~{2,}", "", text)
    text = re.sub(r"[^a-zA-Z\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def lemmatize_text(text):
    tokens = word_tokenize(text)
    pos_tags = nltk.pos_tag(tokens)
    lemmas = [
        lemmatizer.lemmatize(token, get_wordnet_pos(tag))
        for token, tag in pos_tags
        if token not in FINAL_STOPWORDS and len(token) >= 3 and token.isalpha()
    ]
    return " ".join(lemmas)


def preprocess(text):
    return lemmatize_text(clean_text(text))
