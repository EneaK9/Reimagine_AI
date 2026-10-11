import 'dart:async';
import 'package:flutter/foundation.dart';
import '../services/api_service.dart';

/// Result of an editor action: the scene data to push into the editor (null
/// when nothing changed) and a message for the user.
typedef SceneActionResult = (Map<String, dynamic>? data, String message);

/// State for the editable 3D room scene.
///
/// The three.js editor in the WebView is the view; this provider is the
/// bridge to the backend: it loads the scene + catalog, queues edit
/// operations coming from the editor (debounced batch save), and handles
/// undo (server-side version snapshots) and AI edits.
///
/// Every server mutation (op batches, undo, AI edit, enhance) runs through
/// one queue, one at a time, so the version captured before each call is
/// the real previous version and undo always targets the right snapshot.
class SceneProvider extends ChangeNotifier {
  final ApiService _apiService = ApiService();

  Map<String, dynamic>? _scene; // full SceneResponse json
  Map<String, dynamic>? _catalog;
  bool _isLoading = false;
  bool _isSaving = false;
  bool _isUndoing = false;
  bool _isAiEditing = false;
  bool _isEnhancing = false;
  DateTime? _enhanceStartedAt;
  String? _error;
  String? _loadError;
  String? _saveError;

  final List<Map<String, dynamic>> _pendingOps = [];
  Timer? _saveTimer;
  final List<int> _undoStack = []; // versions we can revert to

  /// Tail of the mutation queue (never completes with an error).
  Future<void> _mutations = Future.value();

  /// Bumped whenever another scene (or none) is loaded; results that arrive
  /// for an older session are ignored.
  int _session = 0;
  bool _disposed = false;

  // ---- getters ----
  Map<String, dynamic>? get scene => _scene;
  Map<String, dynamic>? get sceneData => _scene?['data'];
  Map<String, dynamic>? get catalog => _catalog;
  String? get sceneId => _scene?['scene_id'];
  int get version => _scene?['version'] ?? 0;
  bool get isLoading => _isLoading;

  /// Edits are being saved or are waiting to be saved (false once a save
  /// failed — see [saveError]).
  bool get isSaving =>
      _isSaving || (_pendingOps.isNotEmpty && _saveError == null);
  bool get hasUnsavedChanges => _pendingOps.isNotEmpty;
  bool get isUndoing => _isUndoing;
  bool get isAiEditing => _isAiEditing;
  bool get isEnhancing => _isEnhancing;
  DateTime? get enhanceStartedAt => _enhanceStartedAt;

  /// An undo, AI edit or enhance is running (only one at a time).
  bool get isBusy => _isUndoing || _isAiEditing || _isEnhancing;
  bool get canUndo => _undoStack.isNotEmpty;

  /// Most recent error of any kind.
  String? get error => _error;

  /// The scene could not be loaded (the editor has nothing to show).
  String? get loadError => _loadError;

  /// The latest edits could not be saved; they are still queued and are
  /// retried by [flushOps] or the next edit.
  String? get saveError => _saveError;

  /// Load a scene and the editor catalog. The previous scene is cleared
  /// first, so a stale scene is never exposed while loading.
  Future<void> loadScene(String id) async {
    final reloadingSameScene = sceneId == id;
    final previousMutations = _resetSession();
    final session = _session;
    _isLoading = true;
    _notify();
    try {
      if (reloadingSameScene) {
        // Edits from the editor that was just closed may still be saving;
        // give them a moment to land so the fresh copy includes them.
        await previousMutations.timeout(
          const Duration(seconds: 5),
          onTimeout: () {},
        );
      }
      final results = await Future.wait([
        _apiService.getScene(id),
        _apiService.getSceneCatalog(),
      ]);
      if (session != _session) return;
      _scene = results[0];
      _catalog = results[1];
    } catch (e) {
      if (session != _session) return;
      _loadError = e.toString();
      _error = _loadError;
    } finally {
      if (session == _session) {
        _isLoading = false;
        _notify();
      }
    }
  }

  /// Set a scene that was just generated (avoids a refetch).
  Future<void> setGeneratedScene(Map<String, dynamic> sceneResponse) async {
    unawaited(_resetSession());
    final session = _session;
    _scene = sceneResponse;
    _notify();
    if (_catalog != null) return;
    try {
      final catalog = await _apiService.getSceneCatalog();
      if (session == _session) _catalog = catalog;
    } catch (e) {
      // Not fatal: the room still renders, only "add furniture" is empty.
      if (session == _session) _error = 'Could not load the catalog: $e';
    }
    if (session == _session) _notify();
  }

  /// Queue an op coming from the editor; saved in a debounced batch.
  void queueOp(Map<String, dynamic> op) {
    if (sceneId == null) return;
    _pendingOps.add(op);
    _notify();
    _saveTimer?.cancel();
    _saveTimer = Timer(const Duration(milliseconds: 900), () {
      _saveTimer = null;
      unawaited(flushOps());
    });
  }

  /// Push pending ops to the backend as one version bump per batch.
  ///
  /// Only one save is in flight at a time; ops that arrive meanwhile go out
  /// in the next batch as soon as it completes. Returns false if saving
  /// failed: the ops are put back at the front of the queue and
  /// [saveError] is set, so edits are never silently dropped.
  Future<bool> flushOps() {
    _cancelSaveTimer();
    final session = _session;
    return _exclusive(() => _savePending(session));
  }

  /// Undo the last saved change (revert to the previous server snapshot).
  /// Returns the reverted scene data to push into the editor, or an error
  /// message.
  Future<(Map<String, dynamic>?, String?)> undo() async {
    if (sceneId == null || _undoStack.isEmpty) return (null, null);
    if (isBusy) return (null, 'Please wait for the current action to finish.');
    final session = _session;
    _cancelSaveTimer();
    _isUndoing = true;
    _notify();
    try {
      final (data, error) =
          await _exclusive<(Map<String, dynamic>?, String?)>(() async {
        // Save first so undo targets the change the user just made.
        if (!await _savePending(session)) {
          return (null, 'Undo cancelled: your latest changes are not saved yet.');
        }
        final id = sceneId;
        if (session != _session || id == null || _undoStack.isEmpty) {
          return (null, null);
        }
        final target = _undoStack.last;
        try {
          final reverted = await _apiService.revertScene(id, target);
          if (session != _session) return (null, null);
          _undoStack.removeLast(); // only once the revert succeeded
          _scene = reverted;
          return (sceneData, null);
        } catch (e) {
          if (session == _session) _error = 'Undo failed: $e';
          return (null, 'Undo failed: $e');
        }
      });
      if (data == null) return (null, error);
      return (await _withQueuedEdits(session, data), null);
    } finally {
      if (session == _session) {
        _isUndoing = false;
        _notify();
      }
    }
  }

  /// Apply a plain-English edit. Returns (newSceneData, message).
  Future<SceneActionResult> nlEdit(String instruction) async {
    if (sceneId == null) return (null, 'No scene loaded');
    if (isBusy) return (null, 'Please wait for the current action to finish.');
    final session = _session;
    _cancelSaveTimer();
    _isAiEditing = true;
    _notify();
    try {
      final (data, message) = await _exclusive<SceneActionResult>(() async {
        if (!await _savePending(session)) {
          return (null, 'Your latest changes could not be saved, so the AI edit was not applied.');
        }
        final id = sceneId;
        if (session != _session || id == null) return (null, 'The room changed.');
        final previousVersion = version;
        try {
          final result = await _apiService.sceneNlEdit(id, instruction);
          if (session != _session) return (null, 'The room changed.');
          final applied = (result['applied_ops'] as List?) ?? [];
          if (applied.isEmpty) {
            return (null, result['message'] as String? ?? 'No change applied');
          }
          _undoStack.add(previousVersion);
          _scene = {
            ...?_scene,
            'version': result['version'],
            'data': result['data'],
          };
          return (sceneData, result['message'] as String? ?? 'Done');
        } catch (e) {
          if (session == _session) _error = 'AI edit failed: $e';
          return (null, 'AI edit failed: $e');
        }
      });
      if (data == null) return (null, message);
      return (await _withQueuedEdits(session, data), message);
    } finally {
      if (session == _session) {
        _isAiEditing = false;
        _notify();
      }
    }
  }

  /// Replace stand-in furniture with AI-generated meshes from the photo.
  /// Can take several minutes. Returns (newSceneData, message).
  Future<SceneActionResult> enhance() async {
    if (sceneId == null) return (null, 'No scene loaded');
    if (isBusy) return (null, 'Please wait for the current action to finish.');
    final session = _session;
    _cancelSaveTimer();
    _isEnhancing = true;
    _enhanceStartedAt = DateTime.now();
    _notify();
    try {
      final (data, message) = await _exclusive<SceneActionResult>(() async {
        if (!await _savePending(session)) {
          return (null, 'Your latest changes could not be saved, so realistic furniture was not started.');
        }
        final id = sceneId;
        if (session != _session || id == null) return (null, 'The room changed.');
        final previousVersion = version;
        try {
          final updated = await _apiService.enhanceScene(id);
          if (session != _session) return (null, 'The room changed.');
          _undoStack.add(previousVersion);
          _scene = updated;
          return (sceneData, 'Realistic furniture applied');
        } catch (e) {
          if (session == _session) _error = 'Realistic furniture failed: $e';
          return (null, e.toString());
        }
      });
      if (data == null) return (null, message);
      return (await _withQueuedEdits(session, data), message);
    } finally {
      if (session == _session) {
        _isEnhancing = false;
        _enhanceStartedAt = null;
        _notify();
      }
    }
  }

  void clear() {
    unawaited(_resetSession());
    _notify();
  }

  // ---- internals ----

  /// Run [task] after every mutation queued before it has finished.
  Future<T> _exclusive<T>(Future<T> Function() task) {
    final result = _mutations.then((_) => task());
    _mutations = result.then<void>((_) {}, onError: (Object _) {});
    return result;
  }

  /// Save all queued ops, one batch at a time. Must run inside [_exclusive].
  Future<bool> _savePending(int session) async {
    while (session == _session && _pendingOps.isNotEmpty) {
      final id = sceneId;
      if (id == null) return false;
      final ops = List<Map<String, dynamic>>.of(_pendingOps);
      _pendingOps.clear();
      final previousVersion = version;
      _isSaving = true;
      _notify();
      try {
        final updated = await _apiService.applySceneOps(id, ops);
        if (session != _session) return true;
        _scene = updated;
        _undoStack.add(previousVersion);
        _saveError = null;
      } catch (e) {
        if (session != _session) return false;
        _pendingOps.insertAll(0, ops); // keep the edits for a retry
        _saveError = 'Could not save your latest changes: $e';
        _error = _saveError;
        return false;
      } finally {
        if (session == _session) {
          _isSaving = false;
          _notify();
        }
      }
    }
    return true;
  }

  /// Edits made in the editor while an action ran are still queued. Save
  /// them and return the latest scene, so refreshing the editor with the
  /// action's result doesn't wipe them.
  Future<Map<String, dynamic>> _withQueuedEdits(
    int session,
    Map<String, dynamic> actionData,
  ) async {
    if (session != _session || _pendingOps.isEmpty) return actionData;
    if (!await flushOps() || session != _session) return actionData;
    return sceneData ?? actionData;
  }

  void _cancelSaveTimer() {
    _saveTimer?.cancel();
    _saveTimer = null;
  }

  /// Forget the current scene: queued ops, undo history, busy flags and
  /// errors all belong to it. Edits still waiting to be saved are sent in
  /// the background, after whatever was already running for that scene.
  /// Returns a future that completes when the old scene's work is done.
  Future<void> _resetSession() {
    _cancelSaveTimer();
    final orphanedSceneId = sceneId;
    final orphanedOps = List<Map<String, dynamic>>.of(_pendingOps);
    if (orphanedSceneId != null && orphanedOps.isNotEmpty) {
      unawaited(_exclusive(
        () => _apiService.applySceneOps(orphanedSceneId, orphanedOps),
      ).then<void>(
        (_) {},
        onError: (Object e) =>
            debugPrint('[Scene] Could not save queued edits: $e'),
      ));
    }
    final previousMutations = _mutations;
    _session++;
    _mutations = Future.value();
    _scene = null;
    _pendingOps.clear();
    _undoStack.clear();
    _isLoading = false;
    _isSaving = false;
    _isUndoing = false;
    _isAiEditing = false;
    _isEnhancing = false;
    _enhanceStartedAt = null;
    _error = null;
    _loadError = null;
    _saveError = null;
    return previousMutations;
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _cancelSaveTimer();
    super.dispose();
  }
}
