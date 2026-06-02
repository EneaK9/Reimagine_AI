import 'dart:async';
import 'dart:convert';
import 'dart:html' as html;
import 'dart:js' as js;
import 'dart:js_util' as js_util;
import 'dart:typed_data';
import 'dart:ui_web' as ui_web;

import 'package:flutter/widgets.dart';
import 'package:image_picker/image_picker.dart';

class WebCameraCaptureController {
  WebCameraCaptureController()
      : _viewType = 'web-camera-${DateTime.now().microsecondsSinceEpoch}';

  final String _viewType;
  html.VideoElement? _video;
  html.MediaStream? _stream;
  Completer<void>? _startCompleter;

  Widget buildPreview() => HtmlElementView(viewType: _viewType);

  /// Call this synchronously from a click handler - do NOT await anything before calling.
  /// Returns a Future that completes when the camera is ready or fails.
  Future<void> start() {
    // Create completer to track async result
    final completer = Completer<void>();
    _startCompleter = completer;

    // Get mediaDevices synchronously
    final mediaDevices = html.window.navigator.mediaDevices;
    if (mediaDevices == null) {
      completer.completeError(
        UnsupportedError('This browser does not support camera access.'),
      );
      return completer.future;
    }

    // Call getUserMedia IMMEDIATELY - no awaits before this!
    // This preserves the user gesture context on mobile browsers.
    final constraints = js_util.jsify({
      'audio': false,
      'video': {
        'facingMode': {'ideal': 'environment'},
      },
    });

    final promise = js_util.callMethod<Object>(
      mediaDevices,
      'getUserMedia',
      [constraints],
    );

    // Handle the promise result with then/catch to avoid breaking gesture context
    js_util.promiseToFuture<html.MediaStream>(promise).then((stream) {
      _onStreamAcquired(stream, completer);
    }).catchError((error) {
      // Try fallback without facingMode constraint
      _tryFallbackStream(mediaDevices, completer, error);
    });

    return completer.future;
  }

  void _onStreamAcquired(html.MediaStream stream, Completer<void> completer) {
    final video = html.VideoElement()
      ..autoplay = true
      ..muted = true
      ..style.width = '100%'
      ..style.height = '100%'
      ..style.objectFit = 'cover'
      ..setAttribute('playsinline', 'true');

    ui_web.platformViewRegistry.registerViewFactory(_viewType, (_) => video);

    _video = video;
    _stream = stream;
    video.srcObject = stream;

    completer.complete();
  }

  void _tryFallbackStream(
    html.MediaDevices mediaDevices,
    Completer<void> completer,
    Object originalError,
  ) {
    final message = originalError.toString();
    // Don't retry permission errors - they won't succeed with different constraints
    if (message.contains('NotAllowedError') || message.contains('Permission')) {
      completer.completeError(originalError);
      return;
    }

    // Try simpler constraints as fallback
    final fallbackConstraints = js_util.jsify({
      'audio': false,
      'video': true,
    });

    final promise = js_util.callMethod<Object>(
      mediaDevices,
      'getUserMedia',
      [fallbackConstraints],
    );

    js_util.promiseToFuture<html.MediaStream>(promise).then((stream) {
      _onStreamAcquired(stream, completer);
    }).catchError((error) {
      completer.completeError(error);
    });
  }

  Future<void> playPreview() async {
    try {
      await _video?.play();
    } catch (_) {
      // Autoplay can be flaky on mobile browsers; the stream is still available
      // and the capture button can retry once the element is attached.
    }
  }

  Future<String> diagnosticsForError(Object error) async {
    final lines = <String>[
      'Error type: ${error.runtimeType}',
      'Error text: $error',
      'DOM name: ${_safeJsString(error, 'name')}',
      'DOM message: ${_safeJsString(error, 'message')}',
      'URL: ${html.window.location.href}',
      'Origin: ${html.window.location.origin}',
      'Protocol: ${html.window.location.protocol}',
      'Secure context: ${_safeWindowProperty('isSecureContext')}',
      'Top-level window: ${_isTopLevelWindow()}',
      'mediaDevices available: ${html.window.navigator.mediaDevices != null}',
      'User agent: ${html.window.navigator.userAgent}',
    ];

    final cameraPermission = await _cameraPermissionState();
    if (cameraPermission != null) {
      lines.add('Permissions API camera state: $cameraPermission');
    }

    final policyCamera = _permissionsPolicyAllowsCamera();
    if (policyCamera != null) {
      lines.add('Permissions Policy allows camera: $policyCamera');
    }

    return lines.join('\n');
  }


  String _safeJsString(Object target, String property) {
    try {
      final value = js_util.getProperty<Object?>(target, property);
      return value?.toString() ?? 'unavailable';
    } catch (_) {
      return 'unavailable';
    }
  }

  String _safeWindowProperty(String property) {
    try {
      final value = js_util.getProperty<Object?>(html.window, property);
      return value?.toString() ?? 'unavailable';
    } catch (_) {
      return 'unavailable';
    }
  }

  bool _isTopLevelWindow() {
    try {
      return identical(html.window, html.window.top);
    } catch (_) {
      return false;
    }
  }

  Future<String?> _cameraPermissionState() async {
    try {
      final permissions = js_util.getProperty<Object?>(html.window.navigator, 'permissions');
      if (permissions == null) return null;

      final promise = js_util.callMethod<Object>(permissions, 'query', [
        js_util.jsify({'name': 'camera'}),
      ]);
      final status = await js_util.promiseToFuture<Object>(promise);
      return _safeJsString(status, 'state');
    } catch (_) {
      return null;
    }
  }

  bool? _permissionsPolicyAllowsCamera() {
    try {
      final document = html.document;
      final policy = js_util.getProperty<Object?>(
        document,
        'permissionsPolicy',
      ) ?? js_util.getProperty<Object?>(document, 'featurePolicy');
      if (policy == null) return null;

      if (js_util.hasProperty(policy, 'allowsFeature')) {
        return js_util.callMethod<bool>(policy, 'allowsFeature', ['camera']);
      }
      if (js_util.hasProperty(policy, 'allowedFeatures')) {
        final features = js_util.callMethod<Object>(policy, 'allowedFeatures', []);
        return js_util.callMethod<bool>(features, 'includes', ['camera']);
      }
    } catch (_) {
      return null;
    }
    return null;
  }

  Future<XFile> capture() async {
    final video = _video;
    if (video == null) {
      throw StateError('Camera has not been started.');
    }

    final width = video.videoWidth > 0 ? video.videoWidth : 1280;
    final height = video.videoHeight > 0 ? video.videoHeight : 720;
    final canvas = html.CanvasElement(width: width, height: height);
    canvas.context2D.drawImageScaled(video, 0, 0, width, height);

    final dataUrl = canvas.toDataUrl('image/jpeg', 0.92);
    final commaIndex = dataUrl.indexOf(',');
    final base64Image = commaIndex >= 0 ? dataUrl.substring(commaIndex + 1) : dataUrl;
    final bytes = Uint8List.fromList(base64Decode(base64Image));

    return XFile.fromData(
      bytes,
      name: 'web-camera-${DateTime.now().millisecondsSinceEpoch}.jpg',
      mimeType: 'image/jpeg',
    );
  }

  void dispose() {
    final stream = _stream;
    if (stream != null) {
      for (final track in stream.getTracks()) {
        track.stop();
      }
    }
    _stream = null;

    final video = _video;
    if (video != null) {
      video.pause();
      video.srcObject = null;
      video.remove();
    }
    _video = null;
  }
}
