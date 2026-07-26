import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../config/api_config.dart';
import '../providers/auth_provider.dart';
import '../providers/scene_provider.dart';
import '../screens/scene_editor_screen.dart';

/// Open the interactive 3D room editor.
///
/// Mobile: pushes [SceneEditorScreen] (WebView + JS bridge).
/// Web: flutter_inappwebview has no bridge support in browsers, so the
/// editor opens in a new tab in standalone mode (?scene_id=&token=) and
/// talks to the backend API directly.
Future<void> openSceneEditor(BuildContext context, {String? sceneId}) async {
  if (kIsWeb) {
    final id = sceneId ?? context.read<SceneProvider>().sceneId;
    if (id == null) return;
    final token = context.read<AuthProvider>().token ?? '';
    final url = Uri.parse(
      '${ApiConfig.baseUrl}/editor?scene_id=$id&token=$token',
    );
    await launchUrl(url, webOnlyWindowName: '_blank');
    return;
  }

  await Navigator.push(
    context,
    MaterialPageRoute(builder: (_) => SceneEditorScreen(sceneId: sceneId)),
  );
}
