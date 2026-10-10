from app.github_review import ReviewCandidate
from app.review_queue import ReviewQueue

def test_queue_is_deduplicated_and_persistent(tmp_path):
    path=str(tmp_path/"reviews.db")
    q=ReviewQueue(path)
    candidate=ReviewCandidate("owner/repo",3,"a"*40,"main","synchronize")
    assert q.enqueue(candidate)
    assert not q.enqueue(candidate)
    assert q.status("owner/repo",3,"a"*40)=="pending"
    q.close()
    q=ReviewQueue(path)
    assert q.approve("owner/repo",3,"a"*40)
    assert q.status("owner/repo",3,"a"*40)=="approved"
    assert not q.approve("owner/repo",3,"a"*40)
    q.close()
