from dataclasses import asdict, is_dataclass

from backend.services.analysis_service import AnalysisService


def main():
    service = AnalysisService()

    service.initialize()

    try:
        analysis_response = service.execute(
            input_path="data/banking/banking_new_customers.csv",
            mode="auto",
        )

        print("\n========== SMOKE TEST ==========")
        print("Type:", type(analysis_response))
        print("Is Dataclass:", is_dataclass(analysis_response))

        if is_dataclass(analysis_response):
            print(asdict(analysis_response))
        else:
            print(analysis_response)

    finally:
        service.shutdown()


if __name__ == "__main__":
    main()