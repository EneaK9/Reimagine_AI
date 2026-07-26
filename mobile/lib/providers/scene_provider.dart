import 'dart:async';
import 'package:flutter/foundation.dart';
import '../services/api_service.dart';

/// State for the editable 3D room scene.
///
/// The three.js editor in the WebView is the view; this provider is the
/// bridge to the backend: it loads the scene + catalog, queues edit
/// operations coming from the editor (debounced batch save), and handles
/// undo (server-side version snapshots) and AI edits.
class SceneProvider extends ChangeNotifier {
  final ApiService _apiService = ApiService();

  Map<String, dynamic>? _scene; // full SceneResponse json
  Map<String, dynamic>? _catalog;
  bool _isLoading = false;
  bool _isSaving = false;
  String? _error;

  final List<Map<String, dynamic>> _pendingOps = [];
  Timer? _saveTimer;
  final List<int> _undoStack = []; // versions we can revert to

  // ---- getters ----
  Map<String, dynamic>? get scene => _scene;
  Map<String, dynamic>? get sceneData => _scene?['data'];
  Map<String, dynamic>? get catalog => _catalog;
  String? get sceneId => _scene?['scene_id'];
  int get version => _scene?['version'] ?? 0;
  bool get isLoading => _isLoading;
  bool get isSaving => _isSaving || _pendingOps.isNotEmpty;
  bool get canUndo => _undoStack.isNotEmpty;
  String? get error => _error;

  /// Load a scene and the editor catalog.
  Future<void> loadScene(String sceneId) async {
    _isLoading = true;
    _error = null;
    _undoStack.clear();
    _pendingOps.clear();
    notifyListeners();
    try {
      final results = await Future.wait([
        _apiService.getScene(sceneId),
        _apiService.getSceneCatalog(),
      ]);
      _scene = results[0];
      _catalog = results[1];
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Set a scene that was just generated (avoids a refetch).
  Future<void> setGeneratedScene(Map<String, dynamic> sceneResponse) async {
    _scene = sceneResponse;
    _undoStack.clear();
    _pendingOps.clear();
    _error = null;
    try {
      _catalog ??= await _apiService.getSceneCatalog();
    } catch (e) {
      _error = e.toString();
    }
    notifyListeners();
  }

  /// Queue an op coming from the editor; saved in a debounced batch.
  void queueOp(Map<String, dynamic> op) {
    if (sceneId == null) return;
    _pendingOps.add(op);
    notifyListeners();
    _saveTimer?.cancel();
    _saveTimer = Timer(const Duration(milliseconds: 900), flushOps);
  }

  /// Push pending ops to the backend as one version bump.
  Future<void> flushOps() async {
    if (sceneId == null || _pendingOps.isEmpty) return;
    final ops = List<Map<String, dynamic>>.from(_pendingOps);
    _pendingOps.clear();
    _isSaving = true;
    notifyListeners();
    try {
      final previousVersion = version;
      _scene = await _apiService.applySceneOps(sceneId!, ops);
      _undoStack.add(previousVersion);
    } catch (e) {
      _error = 'Save failed: $e';
    } finally {
      _isSaving = false;
      notifyListeners();
    }
  }

  /// Undo the last saved batch (revert to the previous server snapshot).
  /// Returns the fresh scene data to push into the editor, or null.
  Future<Map<String, dynamic>?> undo() async {
    if (sceneId == null || _undoStack.isEmpty) return null;
    await flushOps();
    final target = _undoStack.removeLast();
    _isSaving = true;
    notifyListeners();
    try {
      _scene = await _apiService.revertScene(sceneId!, target);
      return sceneData;
    } catch (e) {
      _error = 'Undo failed: $e';
      return null;
    } finally {
      _isSaving = false;
      notifyListeners();
    }
  }

  /// Apply a plain-English edit. Returns (newSceneData, message).
  Future<(Map<String, dynamic>?, String)> nlEdit(String instruction) async {
    if (sceneId == null) return (null, 'No scene loaded');
    await flushOps();
    _isSaving = true;
    notifyListeners();
    try {
      final previousVersion = version;
      final result = await _apiService.sceneNlEdit(sceneId!, instruction);
      final applied = (result['applied_ops'] as List?) ?? [];
      if (applied.isNotEmpty) {
        _undoStack.add(previousVersion);
        _scene = {
          ...?_scene,
          'version': result['version'],
          'data': result['data'],
        };
        return (sceneData, result['message'] as String? ?? 'Done');
      }
      return (null, result['message'] as String? ?? 'No change applied');
    } catch (e) {
      _error = 'AI edit failed: $e';
      return (null, 'AI edit failed: $e');
    } finally {
      _isSaving = false;
      notifyListeners();
    }
  }

  void clear() {
    _saveTimer?.cancel();
    _scene = null;
    _pendingOps.clear();
    _undoStack.clear();
    _error = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _saveTimer?.cancel();
    super.dispose();
  }
}
