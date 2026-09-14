using System.Collections;
using UnityEngine;

namespace TEP.DigitalTwin
{
    public sealed class MockPredictionSource : PredictionSource
    {
        [SerializeField] private TextAsset mockSequence;
        [SerializeField, Min(0.2f)] private float intervalSeconds = 2f;
        [SerializeField] private bool loop = true;

        private Coroutine playback;

        private void OnEnable() => playback = StartCoroutine(Play());

        private void OnDisable()
        {
            if (playback != null) StopCoroutine(playback);
        }

        private IEnumerator Play()
        {
            if (mockSequence == null) yield break;
            var sequence = JsonUtility.FromJson<PredictionSequence>(mockSequence.text);
            if (sequence?.snapshots == null || sequence.snapshots.Length == 0) yield break;

            // Give the controller one frame to subscribe before the first snapshot.
            yield return null;

            do
            {
                foreach (var snapshot in sequence.snapshots)
                {
                    Publish(snapshot);
                    yield return new WaitForSeconds(intervalSeconds);
                }
            } while (loop);
        }
    }
}
