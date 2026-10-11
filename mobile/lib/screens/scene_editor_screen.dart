import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../config/api_config.dart';
import '../providers/auth_provider.dart';
import '../providers/scene_provider.dart';
import '../theme/app_theme.dart';

const _editorBackground = Color(0xFF14120F);
const _editorAccent = Color(0xFFC98E5A);

/// Interactive 3D room editor.
///
/// Hosts the three.js editor served by the backend at
/// `${ApiConfig.baseUrl}/editor` in a WebView. When the page calls the
/// `ready` handler, the scene is pushed with
/// `window.RAI.loadScene(data, catalog, {apiBase, token, sceneId})` (the
/// options let the editor fetch the room photo for its compare overlay).
/// The editor renders the structured scene (room shell + one node per
/// furniture object) and sends edit operations back over the JS bridge
/// (`op`, `selection`); this screen persists them via [SceneProvider].
class SceneEditorScreen extends StatefulWidget {
  final String? sceneId;

  /// Pass [sceneId] to load a scene from the backend, or nothing to edit the
  /// scene [SceneProvider] already holds (e.g. one that was just generated).
  const SceneEditorScreen({super.key, this.sceneId});

  @override
  State<SceneEditorScreen> createState() => _SceneEditorScreenState();
}

class _SceneEditorScreenState extends State<SceneEditorScreen> {
  /// How long the editor page may take to report `ready`.
  static const _readyTimeout = Duration(seconds: 25);

  late final SceneProvider _provider;
  InAppWebViewController? _webView;
  Key _webViewKey = UniqueKey();
  Timer? _readyTimer;
  bool _editorReady = false;
  bool _scenePushed = false;
  String? _editorError;

  /// Whether the scene this screen shows is loaded in the provider: always
  /// for a freshly generated scene, after [SceneProvider.loadScene] otherwise.
  late bool _sceneLoaded;

  @override
  void initState() {
    super.initState();
    _provider = context.read<SceneProvider>();
    _sceneLoaded = widget.sceneId == null;
    _startReadyTimer();
    if (widget.sceneId != null) {
      // After the first frame: loading notifies the provider's listeners.
      WidgetsBinding.instance.addPostFrameCallback((_) => _loadScene());
    }
  }

  @override
  void dispose() {
    _readyTimer?.cancel();
    // Save any queued edits; the provider outlives this screen.
    unawaited(_provider.flushOps());
    super.dispose();
  }

  // ---- scene loading / JS bridge ----

  Future<void> _loadScene() async {
    final id = widget.sceneId;
    if (id == null || !mounted) return;
    setState(() {
      _sceneLoaded = false;
      _scenePushed = false;
    });
    // Clears the previous scene before fetching, so nothing stale is pushed.
    await _provider.loadScene(id);
    if (!mounted) return;
    setState(() => _sceneLoaded = true);
    _pushSceneIfReady();
  }

  void _pushSceneIfReady() {
    if (!mounted || !_editorReady || !_sceneLoaded) return;
    final controller = _webView;
    final data = _provider.sceneData;
    final sceneId = _provider.sceneId;
    if (controller == null || data == null || sceneId == null) return;
    if (widget.sceneId != null && sceneId != widget.sceneId) return;

    final catalog = _provider.catalog ?? {'entries': []};
    final opts = {
      'apiBase': ApiConfig.baseUrl,
      'token': context.read<AuthProvider>().token,
      'sceneId': sceneId,
    };
    controller.evaluateJavascript(
      source: 'window.RAI.loadScene(${jsonEncode(data)}, '
          '${jsonEncode(catalog)}, ${jsonEncode(opts)});',
    );
    setState(() => _scenePushed = true);
  }

  void _refreshEditorScene(Map<String, dynamic> sceneData) {
    final controller = _webView;
    if (controller == null || !_scenePushed) return;
    controller.evaluateJavascript(
      source: 'window.RAI.refreshScene(${jsonEncode(sceneData)});',
    );
  }

  void _onWebViewCreated(InAppWebViewController controller) {
    _webView = controller;
    controller.addJavaScriptHandler(
      handlerName: 'ready',
      callback: (_) {
        _readyTimer?.cancel();
        if (!mounted) return null;
        setState(() {
          _editorReady = true;
          _editorError = null;
          _scenePushed = false; // a (re)loaded page needs the scene again
        });
        _pushSceneIfReady();
        return null;
      },
    );
    controller.addJavaScriptHandler(
      handlerName: 'op',
      callback: (args) {
        if (mounted && _scenePushed && args.isNotEmpty && args.first is Map) {
          _provider.queueOp(Map<String, dynamic>.from(args.first as Map));
        }
        return null;
      },
    );
    controller.addJavaScriptHandler(
      handlerName: 'selection',
      callback: (_) => null,
    );
  }

  // ---- editor page failures ----

  void _startReadyTimer() {
    _readyTimer?.cancel();
    _readyTimer = Timer(_readyTimeout, () {
      if (!_editorReady) {
        _onEditorFailed(
          'The 3D editor is taking too long to start. '
          'Check your connection and try again.',
        );
      }
    });
  }

  void _onEditorFailed(String message) {
    _readyTimer?.cancel();
    if (!mounted || _editorError != null) return;
    setState(() {
      _editorError = message;
      _editorReady = false;
      _scenePushed = false;
    });
  }

  /// Retry whatever failed: reload the editor page and/or the scene.
  void _retry() {
    if (_editorError != null) {
      // A fresh WebView gives a fresh page load and bridge handlers.
      setState(() {
        _editorError = null;
        _editorReady = false;
        _scenePushed = false;
        _webView = null;
        _webViewKey = UniqueKey();
      });
      _startReadyTimer();
    }
    if (widget.sceneId != null && _provider.loadError != null) {
      _loadScene();
    }
  }

  // ---- actions ----

  void _showMessage(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _onUndo() async {
    final (data, error) = await _provider.undo();
    if (!mounted) return;
    if (data != null) _refreshEditorScene(data);
    if (error != null) _showMessage(error);
  }

  Future<void> _onAiEdit() async {
    final controller = TextEditingController();
    final instruction = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppTheme.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('AI edit', style: GoogleFonts.poppins(fontSize: 18)),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLines: 2,
          decoration: const InputDecoration(
            hintText: 'e.g. "move the sofa to the back wall\nand make it navy blue"',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('Apply'),
          ),
        ],
      ),
    );
    if (!mounted || instruction == null || instruction.isEmpty) return;

    _showMessage('Applying AI edit…');
    final (data, message) = await _provider.nlEdit(instruction);
    if (!mounted) return;
    if (data != null) _refreshEditorScene(data);
    _showMessage(message);
  }

  Future<void> _onEnhance() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppTheme.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Make realistic',
            style: GoogleFonts.poppins(fontSize: 18)),
        content: const Text(
          'Generate realistic 3D models of your furniture from the photo? '
          'This can take several minutes; you can keep arranging the room '
          'meanwhile.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Generate'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    // Progress is shown by the banner while provider.isEnhancing.
    final (data, message) = await _provider.enhance();
    if (!mounted) return;
    if (data != null) _refreshEditorScene(data);
    _showMessage(message);
  }

  // ---- UI ----

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<SceneProvider>();
    final canAct = _scenePushed && provider.sceneId != null && !provider.isBusy;
    final overlay = _buildOverlay(provider);

    return Scaffold(
      backgroundColor: _editorBackground,
      appBar: AppBar(
        backgroundColor: _editorBackground,
        foregroundColor: Colors.white,
        elevation: 0,
        title: Text(
          provider.scene?['title'] ?? '3D Room',
          style: GoogleFonts.poppins(fontSize: 16, fontWeight: FontWeight.w600),
        ),
        actions: [
          if (provider.isSaving)
            const Padding(
              padding: EdgeInsets.only(right: 12),
              child: Center(
                child: SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white54,
                  ),
                ),
              ),
            ),
          IconButton(
            tooltip: 'Undo',
            icon: const Icon(Icons.undo),
            onPressed: canAct && provider.canUndo ? _onUndo : null,
          ),
          IconButton(
            tooltip: 'AI edit',
            icon: const Icon(Icons.auto_awesome),
            onPressed: canAct ? _onAiEdit : null,
          ),
          IconButton(
            tooltip: 'Make realistic',
            icon: const Icon(Icons.auto_fix_high),
            onPressed: canAct ? _onEnhance : null,
          ),
        ],
        bottom: provider.isUndoing || provider.isAiEditing
            ? const PreferredSize(
                preferredSize: Size.fromHeight(2),
                child: LinearProgressIndicator(
                  minHeight: 2,
                  color: _editorAccent,
                  backgroundColor: Colors.transparent,
                ),
              )
            : null,
      ),
      body: Stack(
        children: [
          InAppWebView(
            key: _webViewKey,
            initialUrlRequest: URLRequest(
              url: WebUri('${ApiConfig.baseUrl}/editor'),
            ),
            initialSettings: InAppWebViewSettings(
              transparentBackground: true,
              allowFileAccessFromFileURLs: true,
              allowUniversalAccessFromFileURLs: true,
              mediaPlaybackRequiresUserGesture: false,
              disableVerticalScroll: false,
              supportZoom: false,
            ),
            onWebViewCreated: _onWebViewCreated,
            onReceivedError: (controller, request, error) {
              if (request.isForMainFrame == false ||
                  error.type == WebResourceErrorType.CANCELLED) {
                return;
              }
              _onEditorFailed(
                "Couldn't load the 3D editor (${error.description}).",
              );
            },
            onReceivedHttpError: (controller, request, response) {
              if (request.isForMainFrame == false) return;
              final code = response.statusCode;
              _onEditorFailed(
                'The 3D editor is unavailable right now'
                '${code != null ? ' (HTTP $code)' : ''}.',
              );
            },
            onWebContentProcessDidTerminate: (controller) =>
                _onEditorFailed('The 3D editor stopped unexpectedly.'),
            onRenderProcessGone: (controller, detail) =>
                _onEditorFailed('The 3D editor stopped unexpectedly.'),
            onConsoleMessage: (controller, message) {
              debugPrint('[Editor] ${message.message}');
            },
          ),
          if (provider.saveError != null)
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: _SaveErrorBanner(
                saving: provider.isSaving,
                onRetry: () => _provider.flushOps(),
              ),
            ),
          if (provider.isEnhancing)
            Positioned(
              left: 12,
              right: 12,
              bottom: 12,
              child: SafeArea(
                top: false,
                child: _EnhanceBanner(
                  startedAt: provider.enhanceStartedAt ?? DateTime.now(),
                ),
              ),
            ),
          if (overlay != null) Positioned.fill(child: overlay),
        ],
      ),
    );
  }

  Widget? _buildOverlay(SceneProvider provider) {
    if (_editorError != null) {
      return _EditorMessage(
        icon: Icons.wifi_off_rounded,
        message: _editorError!,
        onRetry: _retry,
      );
    }
    if (widget.sceneId != null &&
        provider.loadError != null &&
        !provider.isLoading) {
      return _EditorMessage(
        icon: Icons.error_outline_rounded,
        message: 'Could not load your 3D room.\n${provider.loadError}',
        onRetry: _retry,
      );
    }
    if (!_sceneLoaded || provider.isLoading) {
      return const _EditorLoading(message: 'Loading your 3D room…');
    }
    if (provider.sceneData == null) {
      return const _EditorMessage(
        icon: Icons.chair_outlined,
        message: 'There is no 3D room to show.',
      );
    }
    if (!_scenePushed) {
      return _EditorLoading(
        message: _editorReady ? 'Opening your 3D room…' : 'Starting the 3D editor…',
      );
    }
    return null;
  }
}

class _EditorLoading extends StatelessWidget {
  const _EditorLoading({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: _editorBackground,
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(color: _editorAccent),
            const SizedBox(height: 16),
            Text(
              message,
              textAlign: TextAlign.center,
              style: GoogleFonts.poppins(color: Colors.white70, fontSize: 14),
            ),
          ],
        ),
      ),
    );
  }
}

class _EditorMessage extends StatelessWidget {
  const _EditorMessage({
    required this.icon,
    required this.message,
    this.onRetry,
  });

  final IconData icon;
  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: _editorBackground,
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, color: Colors.white54, size: 40),
              const SizedBox(height: 16),
              Text(
                message,
                textAlign: TextAlign.center,
                style: GoogleFonts.poppins(color: Colors.white70, fontSize: 14),
              ),
              const SizedBox(height: 24),
              if (onRetry != null)
                FilledButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh_rounded),
                  label: const Text('Retry'),
                  style: FilledButton.styleFrom(
                    backgroundColor: _editorAccent,
                    foregroundColor: Colors.white,
                  ),
                ),
              TextButton(
                onPressed: () => Navigator.maybePop(context),
                style: TextButton.styleFrom(foregroundColor: Colors.white60),
                child: const Text('Back'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SaveErrorBanner extends StatelessWidget {
  const _SaveErrorBanner({required this.saving, required this.onRetry});

  final bool saving;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: const Color(0xFF3A211A),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 6, 8, 6),
        child: Row(
          children: [
            const Icon(Icons.cloud_off_rounded, color: _editorAccent, size: 18),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                "Couldn't save your latest changes.",
                style: GoogleFonts.poppins(color: Colors.white, fontSize: 13),
              ),
            ),
            TextButton(
              onPressed: saving ? null : onRetry,
              style: TextButton.styleFrom(foregroundColor: _editorAccent),
              child: Text(saving ? 'Saving…' : 'Retry'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Progress for "Make realistic", shown for as long as it runs.
class _EnhanceBanner extends StatefulWidget {
  const _EnhanceBanner({required this.startedAt});

  final DateTime startedAt;

  @override
  State<_EnhanceBanner> createState() => _EnhanceBannerState();
}

class _EnhanceBannerState extends State<_EnhanceBanner> {
  late final Timer _ticker;

  @override
  void initState() {
    super.initState();
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _ticker.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final elapsed = DateTime.now().difference(widget.startedAt);
    final seconds = (elapsed.inSeconds % 60).toString().padLeft(2, '0');
    return Material(
      color: const Color(0xEE241F1A),
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: _editorAccent,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Generating realistic furniture… '
                    '${elapsed.inMinutes}:$seconds',
                    style: GoogleFonts.poppins(
                      color: Colors.white,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'This can take several minutes. Keep arranging; your '
                    'changes are saved when it finishes.',
                    style: GoogleFonts.poppins(
                      color: Colors.white60,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
