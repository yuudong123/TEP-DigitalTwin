using System;

namespace TEP.DigitalTwin
{
    public enum ProcessStatus { NORMAL, CAUTION, WARNING, CRITICAL }

    [Serializable]
    public sealed class RiskEntry
    {
        public float score;
        public float threshold;
        public bool alert;
    }

    [Serializable]
    public sealed class RiskSet
    {
        public RiskEntry failure_within_4h;
        public RiskEntry failure_within_2h;
        public RiskEntry failure_within_1h;
    }

    [Serializable]
    public sealed class RulEntry { public float hours; }

    [Serializable]
    public sealed class RiskFactor
    {
        public int rank;
        public string feature;
        public string source_feature;
        public string transform;
        public float shap_value;
    }

    [Serializable]
    public sealed class PredictionSnapshot
    {
        public string schema_version;
        public string model_version;
        public string trajectory_key;
        public float timestamp_hours;
        public RulEntry rul;
        public RiskSet risk;
        public string status;
        public string explanation_model;
        public RiskFactor[] top_risk_factors;

        public ProcessStatus Status
        {
            get
            {
                return Enum.TryParse(status, true, out ProcessStatus parsed)
                    ? parsed
                    : ProcessStatus.NORMAL;
            }
        }
    }

    [Serializable]
    public sealed class PredictionSequence { public PredictionSnapshot[] snapshots; }

    [Serializable]
    public sealed class PredictionEnvelope
    {
        public PredictionSnapshot prediction;
        public double received_at_unix_ms;
        public string source_mode;
        public string connection_state;
    }
}
