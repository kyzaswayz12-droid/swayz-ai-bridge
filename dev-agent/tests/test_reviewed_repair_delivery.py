import hashlib
import json
import unittest
from unittest.mock import patch
from agent.supervised_development_cycle import complete_supervised_cycle

class Queue:
    state="queued"
    def get(self, job):
        return {"task":"Fix test","state":self.state}
    def claim(self, job):
        if self.state!="queued": return False
        self.state="claimed"
        return True
    def finish(self, job, state):
        self.state=state

def proposal(name):
    obj={"base_sha":"a"*40,"branch":"agent/"+name,
         "changes":[{"path":"tests/"+name+".py","content":"x=1\n"}]}
    digest=hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")).hexdigest()
    obj["proposal_sha256"]=digest
    return json.dumps(obj),digest

class ReviewedRepairDeliveryTests(unittest.TestCase):
    def execute(self, repair_delivery):
        original, old_digest=proposal("original")
        replacement,new_digest=proposal("repair")
        review=json.dumps({"proposal_sha256":old_digest,"approved":True,"findings":[]})
        q=Queue()
        with patch("agent.supervised_development_cycle.deliver_approved_draft",
                   return_value={"draft":True}) as deliver:
            result=complete_supervised_cycle(
                job_id="job1",task_queue=q,require_running=lambda:None,
                approved_base_sha="a"*40,approved_proposal_sha256=old_digest,
                base_branch="main",coding_response=original,
                review_response=review,github=object(),
                run_verified_tests=lambda **kw:{
                    "state":"passed","cleanup_verified":True,
                    "repair_delivery":repair_delivery(replacement,new_digest)})
        return result,deliver,q,new_digest

    def test_revised_plan_is_delivered(self):
        def approved(raw,digest):
            return {"raw_plan":raw,"proposal_sha256":digest,
                    "review_response":json.dumps({
                        "proposal_sha256":digest,"approved":True,"findings":[]})}
        result,deliver,q,digest=self.execute(approved)
        self.assertEqual(result.state,"done")
        self.assertEqual(deliver.call_args.kwargs["approved_proposal_sha256"],digest)

    def test_unreviewed_repair_never_delivered(self):
        def unapproved(raw,digest):
            return {"raw_plan":raw,"proposal_sha256":digest,
                    "review_response":json.dumps({
                        "proposal_sha256":digest,"approved":False,"findings":[]})}
        with self.assertRaises(PermissionError):
            self.execute(unapproved)

    def test_mismatched_digest_never_delivered(self):
        def wrong(raw,digest):
            return {"raw_plan":raw,"proposal_sha256":"f"*64,
                    "review_response":json.dumps({
                        "proposal_sha256":"f"*64,"approved":True,"findings":[]})}
        with self.assertRaises(PermissionError):
            self.execute(wrong)
