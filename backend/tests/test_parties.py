from app.classify.parties import extract_parties
from app.playbooks.loader import get_playbook


def _names(text, doc_type):
    return [p.name for p in extract_parties(text, get_playbook(doc_type))]


def test_parties_follow_the_between_clause():
    text = ('This Mutual Nondisclosure Agreement (the "Agreement"), dated as of December 2, 2024 is between HilleVax, Inc., '
            'a Delaware corporation ("Company"), and XOMA (US) LLC, a Delaware limited liability company (the "Other Party"). '
            'To explore a transaction between Company and Other Party (the "Possible Transaction"), each party may disclose.')
    assert _names(text, "nda") == ['HilleVax, Inc ("Company")', 'XOMA US LLC ("Other Party")']


def test_sentences_and_signature_blocks_are_not_parties():
    text = ('Fortrea Holdings, Inc. (the "Company")\nDear Peter:\nYou will report to our Chief Executive Officer ("CEO"). '
            'Use of the Spotify Service ("Content") is personal.\nSincerely,\nPeter M. Neupert Fortrea Holdings, Inc.\n')
    parties = extract_parties(text, get_playbook("offer_letter"))
    assert [(p.name, p.role) for p in parties] == [
        ('Fortrea Holdings, Inc ("Company")', "Employer / HR"), ("Peter", "Candidate / Employee")]
