#if UNITY_EDITOR
using System.IO;
using TEP.DigitalTwin;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace TEP.Editor
{
    public static class ProcessOverviewSetup
    {
        public const string ScenePath = "Assets/TEP/Scenes/TEPProcessOverview.unity";

        [MenuItem("TEP Digital Twin/Generate Process Overview")]
        public static void Generate()
        {
            Directory.CreateDirectory("Assets/TEP/Scenes");
            Directory.CreateDirectory("Assets/TEP/Resources");
            AssetDatabase.Refresh();
            var fontImporter = AssetImporter.GetAtPath("Assets/TEP/Resources/NanumGothic-Regular.ttf") as TrueTypeFontImporter;
            if (fontImporter == null) throw new IOException("한글 UI 폰트가 없습니다.");
            fontImporter.fontTextureCase = FontTextureCase.Dynamic;
            fontImporter.includeFontData = true;
            fontImporter.SaveAndReimport();
            const string materialPath = "Assets/TEP/Resources/ProcessSurface.mat";
            if (AssetDatabase.LoadAssetAtPath<Material>(materialPath) == null)
            {
                var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
                AssetDatabase.CreateAsset(new Material(shader), materialPath);
            }
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var root = new GameObject("DigitalTwinRuntime");
            var controller = root.AddComponent<DigitalTwinController>();
            root.AddComponent<WebPredictionBridge>();
            var view = root.AddComponent<ProcessOverview>();
            view.controller = controller;
            view.recordedPrediction = AssetDatabase.LoadAssetAtPath<TextAsset>("Assets/TEP/Mock/recorded_prediction.json");
            // A screenshot preview is an explicit opt-in; default operation waits for Web/API data.
            view.showRecordedPreview = false;
            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
            Debug.Log("TEP_PROCESS_OVERVIEW_READY " + ScenePath);
        }

        [MenuItem("TEP Digital Twin/Build Process Overview WebGL")]
        public static void BuildWebGL()
        {
            if (!File.Exists(ScenePath)) Generate();
            var args = System.Environment.GetCommandLineArgs();
            VerifyBridgeContracts(args);
            var outputIndex = System.Array.IndexOf(args, "-tepWebOutput");
            var output = outputIndex >= 0 && outputIndex + 1 < args.Length
                ? Path.GetFullPath(args[outputIndex + 1])
                : Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "..", "web", "public", "unity"));
            var previous = PlayerSettings.WebGL.compressionFormat;
            try
            {
                PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
                PlayerSettings.WebGL.memorySize = 128;
                PlayerSettings.WebGL.maximumMemorySize = 512;
                PlayerSettings.runInBackground = true;
                var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions { scenes = new[] { ScenePath }, locationPathName = output, target = BuildTarget.WebGL });
                if (report.summary.result != BuildResult.Succeeded) throw new IOException("TEP WebGL build failed: " + report.summary.result);
                Debug.Log("TEP_WEBGL_BUILD_SUCCESS " + output);
            }
            finally { PlayerSettings.WebGL.compressionFormat = previous; }
        }

        private static void VerifyBridgeContracts(string[] args)
        {
            var fixtureIndex = System.Array.IndexOf(args, "-tepFixture");
            if (fixtureIndex < 0 || fixtureIndex + 1 >= args.Length) return;
            var originalJson = File.ReadAllText(args[fixtureIndex + 1]);
            var root = new GameObject("BridgeContractVerification");
            try
            {
                var controller = root.AddComponent<DigitalTwinController>();
                var bridge = root.AddComponent<WebPredictionBridge>();
                var serialized = new SerializedObject(bridge);
                serialized.FindProperty("controller").objectReferenceValue = controller;
                serialized.ApplyModifiedPropertiesWithoutUndo();
                var applied = 0;
                controller.PredictionApplied += _ => applied++;
                var snapshot = JsonUtility.FromJson<PredictionSnapshot>(originalJson);
                var envelope = new PredictionEnvelope { prediction = snapshot, received_at_unix_ms = 1700000000000,
                    source_mode = "api", connection_state = "stale" };
                bridge.ApplyPredictionEnvelope(JsonUtility.ToJson(envelope));
                if (applied != 1) throw new IOException("Unity rejected the real prediction fixture.");
                var loggerEnabled = Debug.unityLogger.logEnabled;
                try
                {
                    Debug.unityLogger.logEnabled = false;
                    snapshot.status = "1";
                    bridge.ApplyPredictionEnvelope(JsonUtility.ToJson(envelope));
                    if (applied != 1) throw new IOException("Unity accepted a numeric status alias.");
                    snapshot.status = "CRITICAL";
                    snapshot.risk.failure_within_1h.score = 1.5f;
                    bridge.ApplyPredictionEnvelope(JsonUtility.ToJson(envelope));
                    if (applied != 1) throw new IOException("Unity accepted an out-of-range probability.");
                    envelope.prediction = JsonUtility.FromJson<PredictionSnapshot>(originalJson);
                    envelope.received_at_unix_ms = 0;
                    bridge.ApplyPredictionEnvelope(JsonUtility.ToJson(envelope));
                    if (applied != 1) throw new IOException("Unity accepted a missing receipt time.");
                }
                finally { Debug.unityLogger.logEnabled = loggerEnabled; }
                Debug.Log("TEP_BRIDGE_CONTRACTS_PASSED real_fixture,numeric_status_rejected,invalid_risk_rejected,receipt_required");
            }
            finally { Object.DestroyImmediate(root); }
        }

        public static void BuildPreview()
        {
            Generate();
            var args = System.Environment.GetCommandLineArgs();
            var index = System.Array.IndexOf(args, "-tepBuild");
            if (index < 0 || index + 1 >= args.Length) throw new IOException("-tepBuild output path required");
            var output = args[index + 1];
            Directory.CreateDirectory(Path.GetDirectoryName(output));
            PlayerSettings.defaultScreenWidth = 1920;
            PlayerSettings.defaultScreenHeight = 1080;
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions { scenes = new[] { ScenePath }, locationPathName = output, target = BuildTarget.StandaloneWindows64 });
            if (report.summary.result != BuildResult.Succeeded) throw new IOException("TEP preview build failed: " + report.summary.result);
            Debug.Log("TEP_PREVIEW_BUILD_SUCCESS " + output);
        }
    }
}
#endif
