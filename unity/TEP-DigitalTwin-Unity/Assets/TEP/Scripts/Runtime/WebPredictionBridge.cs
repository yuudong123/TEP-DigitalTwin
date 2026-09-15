using System;
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

        // Called by the React host through UnityInstance.SendMessage.
        public void ApplyPredictionJson(string json)
        {
            try
            {
                var prediction = JsonUtility.FromJson<PredictionSnapshot>(json);
                if (prediction == null || prediction.rul == null || prediction.risk == null ||
                    string.IsNullOrWhiteSpace(prediction.status))
                    throw new ArgumentException("Prediction JSON is missing required fields.");

                controller.ApplyExternalPrediction(prediction);
            }
            catch (Exception exception)
            {
                Debug.LogError($"Rejected Web prediction: {exception.Message}");
            }
        }
    }
}
