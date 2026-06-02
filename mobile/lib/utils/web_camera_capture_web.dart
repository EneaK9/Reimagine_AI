import 'dart:convert';
import 'dart:html' as html;
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

  Widget buildPreview() => HtmlElementView(viewType: _viewType);

  Future<void> start() async {
    final video = html.VideoElement()
      ..autoplay = true
      ..muted = true
      ..style.width = '100%'
      ..style.height = '100%'
      ..style.objectFit = 'cover'
      ..setAttribute('playsinline', 'true');

    ui_web.platformViewRegistry.registerViewFactory(_viewType, (_) => video);

    final mediaDevices = html.window.navigator.mediaDevices;
    if (mediaDevices == null) {
      throw UnsupportedError('This browser does not support camera access.');
    }

    final stream = await _getCameraStream(mediaDevices);

    _video = video;
    _stream = stream;
    video.srcObject = stream;
  }

  Future<void> playPreview() async {
    try {
      await _video?.play();
    } catch (_) {
      // Autoplay can be flaky on mobile browsers; the stream is still available
      // and the capture button can retry once the element is attached.
    }
  }

  Future<html.MediaStream> _getCameraStream(html.MediaDevices mediaDevices) async {
    try {
      return await mediaDevices.getUserMedia({
        'audio': false,
        'video': {
          'facingMode': {'ideal': 'environment'},
        },
      });
    } catch (e) {
      final message = e.toString();
      if (message.contains('NotAllowedError') || message.contains('Permission')) {
        rethrow;
      }

      return mediaDevices.getUserMedia({
        'audio': false,
        'video': true,
      });
    }
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
