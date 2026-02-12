from celery import shared_task


@shared_task(bind=True)
def generate_dataset_pdf(self, dataset_id: str) -> dict:
    return {
        "success": False,
        "status": "not_implemented",
        "dataset_id": dataset_id,
    }
