from fastapi import APIRouter, HTTPException
from api.schemas import SubjectCreate, SubjectResponse

router = APIRouter()


@router.get("/subjects", response_model=list[SubjectResponse])
def list_subjects():
    from src.subjects import list_subjects as _list
    return _list()


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
def get_subject(subject_id: str):
    from src.subjects import get_subject as _get
    subj = _get(subject_id)
    if not subj:
        raise HTTPException(404, "Subject not found")
    return subj


@router.post("/subjects", response_model=SubjectResponse, status_code=201)
def create_subject(body: SubjectCreate):
    from src.subjects import create_subject as _create
    return _create(body.name)


@router.delete("/subjects/{subject_id}", status_code=204)
def delete_subject(subject_id: str):
    from src.subjects import get_subject, delete_subject as _delete
    from src.vectorstore import delete_collection
    if not get_subject(subject_id):
        raise HTTPException(404, "Subject not found")
    delete_collection(subject_id)
    _delete(subject_id)


@router.put("/subjects/{subject_id}/topics")
def update_topics(subject_id: str, topics: list[str]):
    from src.subjects import update_topics
    update_topics(subject_id, topics)
    return {"ok": True}


@router.delete("/subjects/{subject_id}/topics/{topic}")
def delete_topic(subject_id: str, topic: str):
    from src.subjects import get_subject, update_topics
    subj = get_subject(subject_id)
    if not subj:
        raise HTTPException(404, "Subject not found")
    topics = [t for t in subj.get("topics", []) if t != topic]
    update_topics(subject_id, topics)
    return {"ok": True}
