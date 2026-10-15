using System;
using System.Runtime.InteropServices;
using UnityEngine;

namespace TEP.DigitalTwin
{
    [DisallowMultipleComponent]
    public sealed class WebPredictionBridge : MonoBehaviour
    {
        [SerializeField] private DigitalTwinController controller;

        private void Awake()
        {
            if (controller == null) controller = GetComponent<DigitalTwinController>();
        }

#if UNITY_WEBGL && !UNITY_EDITOR
        [DllImport("__Internal")]
        private static extern void TEP_PredictionApplied(string json);
#endif

        private static bool ValidRisk(RiskEntry risk) => risk != null &&
            !float.IsNaN(risk.score) && !float.IsInfinity(risk.score) && risk.score >= 0 && risk.score <= 1 &&
            !float.IsNaN(risk.threshold) && !float.IsInfinity(risk.threshold) && risk.threshold >= 0 && risk.threshold <= 1;

        private static void Validate(PredictionSnapshot prediction)
        {
            if (prediction == null || prediction.schema_version != "1.0" || prediction.rul == null || prediction.risk == null ||
                string.IsNullOrWhiteSpace(prediction.model_version) || string.IsNullOrWhiteSpace(prediction.trajectory_key) ||
                Array.IndexOf(new[] { "NORMAL", "CAUTION", "WARNING", "CRITICAL" }, prediction.status) < 0 ||
                float.IsNaN(prediction.timestamp_hours) || float.IsInfinity(prediction.timestamp_hours) || prediction.timestamp_hours < 0 ||
                float.IsNaN(prediction.rul.hours) || float.IsInfinity(prediction.rul.hours) || prediction.rul.hours < 0 ||
                !ValidRisk(prediction.risk.failure_within_4h) || !ValidRisk(prediction.risk.failure_within_2h) || !ValidRisk(prediction.risk.failure_within_1h))
                throw new ArgumentException("예측 데이터의 형식이나 값이 올바르지 않습니다.");
        }

        public void ApplyPredictionEnvelope(string json)
        {
            try
            {
                var envelope = JsonUtility.FromJson<PredictionEnvelope>(json);
                if (envelope == null || double.IsNaN(envelope.received_at_unix_ms) || double.IsInfinity(envelope.received_at_unix_ms) ||
                    envelope.received_at_unix_ms <= 0 || (envelope.source_mode != "api" && envelope.source_mode != "mock") ||
                    Array.IndexOf(new[] { "connected", "connecting", "stale", "error", "paused", "mock" }, envelope.connection_state) < 0)
                    throw new ArgumentException("예측 수신 정보가 올바르지 않습니다.");
                Validate(envelope.prediction);
                controller.ApplyExternalPrediction(envelope.prediction);
                GetComponent<ProcessOverview>()?.ApplyConnectionState(envelope.received_at_unix_ms, envelope.source_mode, envelope.connection_state);
#if UNITY_WEBGL && !UNITY_EDITOR
                TEP_PredictionApplied(JsonUtility.ToJson(envelope));
#endif
            }
            catch (Exception exception)
            {
                GetComponent<ProcessOverview>()?.RejectPrediction();
                Debug.LogError($"웹 예측 데이터 거부: {exception.Message}");
            }
        }

        // Called by the React host through UnityInstance.SendMessage.
        public void ApplyPredictionJson(string json)
        {
            try
            {
                var prediction = JsonUtility.FromJson<PredictionSnapshot>(json);
                Validate(prediction);

                controller.ApplyExternalPrediction(prediction);
            }
            catch (Exception exception)
            {
                GetComponent<ProcessOverview>()?.RejectPrediction();
                Debug.LogError($"웹 예측 데이터 거부: {exception.Message}");
            }
        }
    }
}
