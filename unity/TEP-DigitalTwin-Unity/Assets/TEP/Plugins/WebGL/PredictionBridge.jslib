mergeInto(LibraryManager.library, {
  TEP_PredictionApplied: function (jsonPointer) {
    var envelope = JSON.parse(UTF8ToString(jsonPointer));
    window.dispatchEvent(new CustomEvent('tep-unity-prediction', { detail: envelope }));
  }
});
