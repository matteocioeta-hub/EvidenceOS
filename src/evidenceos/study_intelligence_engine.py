from .models import StudyIntelligenceRecord, RelevantStudySet
from .study_classifier import StudyDesignClassifier
from .eligibility_engine import EligibilityEngine
from .study_linker import StudyLinker
class StudyIntelligenceEngine:
    def analyse(self,question,records):
        items=[]; counts={"include":0,"indirect":0,"uncertain":0,"exclude":0}
        for r in records:
            d=StudyDesignClassifier.classify(r); e=EligibilityEngine.predict(question,r,d); counts[e.overall]+=1; items.append(StudyIntelligenceRecord(record=r,design=d,eligibility=e))
        return RelevantStudySet(question_id=question.question_id,records_evaluated=len(records),likely_include=counts["include"],indirect=counts["indirect"],uncertain=counts["uncertain"],excluded=counts["exclude"],study_intelligence=items,study_links=StudyLinker.link(records))
