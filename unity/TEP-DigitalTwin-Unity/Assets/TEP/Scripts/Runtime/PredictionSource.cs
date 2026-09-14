using System;
using UnityEngine;

namespace TEP.DigitalTwin
{
    public abstract class PredictionSource : MonoBehaviour
    {
        public event Action<PredictionSnapshot> PredictionReceived;

        protected void Publish(PredictionSnapshot prediction)
        {
            if (prediction != null)
                PredictionReceived?.Invoke(prediction);
        }
    }
}
