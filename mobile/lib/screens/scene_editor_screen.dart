import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../config/api_config.dart';
import '../providers/scene_provider.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

/// Interactive 3D room editor.
///
/// Hosts the three.js editor (assets/editor/editor.html) in a WebView.
/// The editor renders the structured scene (room shell + one node per
/// furniture object) and sends edit operations back over the JS bridge;
/// this screen persists them via [SceneProvider].
class SceneEditorScreen extends StatefulWidget {
  final String? sceneId;

  /// Pass either [sceneId] (loads from backend) or nothing if the
  /// provider already holds a freshly generated scene.
  const SceneEditorScreen({super.key, this.sceneId});

  @override
  State<SceneEditorScreen> createState() => _SceneEditorScreenState();
}

class _SceneEditorScreenState extends State<SceneEditorScreen> {
  InAppWebViewController? _webView;
  bool _editorReady = false;
  bool _scenePushed = false;
  SceneProvider? _provider;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _provider = context.read<SceneProvider>();
  }

  @override
  void initState() {
    super.initState();
    if (widget.sceneId != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        context.read<SceneProvider>().loadScene(widget.sceneId!).then((_) {
          _pushSceneIfReady();
        });
      });
    }
  }

  void _pushSceneIfReady() {
    final provider = context.read<SceneProvider>();
    if (!_editorReady || _webView == null || provider.sceneData == null) return;
    final data = jsonEncode(provider.sceneData);
    final catalog = jsonEncode(provider.catalog ?? {'entries': []});
    _webView!.evaluateJavascript(
      source: 'window.RAI.loadScene($data, $catalog);',
    );
    setState(() => _scenePushed = true);
  }

  void _refreshEditorScene(Map<String, dynamic> sceneData) {
    if (_webView == null) return;
    _webView!.evaluateJavascript(
      source: 'window.RAI.refreshScene(${jsonEncode(sceneData)});',
    );
  }

  Future<void> _onUndo() async {
    final data = await context.read<SceneProvider>().undo();
    if (data != null) _refreshEditorScene(data);
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
    if (instruction == null || instruction.isEmpty || !mounted) return;

    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(
      const SnackBar(content: Text('Applying AI edit…')),
    );
    final (data, message) = await context.read<SceneProvider>().nlEdit(instruction);
    if (data != null) _refreshEditorScene(data);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(SnackBar(content: Text(message)));
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
          'This takes 1–3 minutes.',
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

    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(const SnackBar(
      content: Text('Generating realistic furniture… (1–3 min)'),
      duration: Duration(minutes: 3),
    ));
    final (data, message) = await context.read<SceneProvider>().enhance();
    messenger.hideCurrentSnackBar();
    if (data != null) _refreshEditorScene(data);
    messenger.showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _onPhotorealRender() async {
    final provider = context.read<SceneProvider>();
    if (_webView == null || provider.sceneId == null) return;

    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(const SnackBar(
      content: Text('Creating photoreal render… (~30s)'),
      duration: Duration(minutes: 2),
    ));

    try {
      // Grab a clean screenshot of the 3D canvas from the editor
      final shot = await _webView!.evaluateJavascript(
        source: 'window.RAI.captureRender();',
      ) as String?;
      if (shot == null || shot.isEmpty) {
        throw Exception('Could not capture the 3D view');
      }

      final image = await ApiService().renderScene(provider.sceneId!, shot);
      messenger.hideCurrentSnackBar();
      if (image == null || !mounted) {
        messenger.showSnackBar(
          const SnackBar(content: Text('Render failed — try again in a minute')),
        );
        return;
      }
      // Show the result inside the editor's overlay viewer
      await _webView!.evaluateJavascript(
        source: 'window.RAI.showRender(${jsonEncode(image)});',
      );
    } catch (e) {
      messenger.hideCurrentSnackBar();
      messenger.showSnackBar(SnackBar(content: Text('Render failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<SceneProvider>();

    return Scaffold(
      backgroundColor: const Color(0xFF14120F),
      appBar: AppBar(
        backgroundColor: const Color(0xFF14120F),
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
            onPressed: provider.canUndo ? _onUndo : null,
          ),
          IconButton(
            tooltip: 'AI edit',
            icon: const Icon(Icons.auto_awesome),
            onPressed: provider.sceneId != null ? _onAiEdit : null,
          ),
          IconButton(
            tooltip: 'Make realistic',
            icon: const Icon(Icons.auto_fix_high),
            onPressed: provider.sceneId != null && !provider.isSaving
                ? _onEnhance
                : null,
          ),
          IconButton(
            tooltip: 'Photoreal render',
            icon: const Icon(Icons.photo_camera),
            onPressed: provider.sceneId != null ? _onPhotorealRender : null,
          ),
        ],
      ),
      body: Stack(
        children: [
          InAppWebView(
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
            onWebViewCreated: (controller) {
              _webView = controller;
              controller.addJavaScriptHandler(
                handlerName: 'ready',
                callback: (_) {
                  _editorReady = true;
                  _pushSceneIfReady();
                  return null;
                },
              );
              controller.addJavaScriptHandler(
                handlerName: 'op',
                callback: (args) {
                  if (args.isNotEmpty && args.first is Map) {
                    context.read<SceneProvider>().queueOp(
                          Map<String, dynamic>.from(args.first as Map),
                        );
                  }
                  return null;
                },
              );
              controller.addJavaScriptHandler(
                handlerName: 'selection',
                callback: (_) => null,
              );
            },
            onConsoleMessage: (controller, message) {
              debugPrint('[Editor] ${message.message}');
            },
          ),
          if (provider.isLoading || (!_scenePushed && provider.sceneData == null))
            Container(
              color: const Color(0xFF14120F),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const CircularProgressIndicator(color: Color(0xFFC98E5A)),
                    const SizedBox(height: 16),
                    Text(
                      provider.error ?? 'Loading your 3D room…',
                      textAlign: TextAlign.center,
                      style: GoogleFonts.poppins(
                        color: Colors.white70,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    // Push any unsaved ops before leaving
    _provider?.flushOps();
    super.dispose();
  }
}
