"""Run all Python analytics and write reports/*.md + analytics.* tables."""
from nova.analytics import causal, descriptive, experiments, forecast, segmentation
from nova.common.report import write


def main():
    write("statistical_analysis.md", descriptive.main())
    write("experiment_readouts.md", experiments.main())
    write("causal_membership.md", causal.main())
    write("customer_segmentation.md", segmentation.main())
    write("revenue_forecast.md", forecast.main())


if __name__ == "__main__":
    main()
