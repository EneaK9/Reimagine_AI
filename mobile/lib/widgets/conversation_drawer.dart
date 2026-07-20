import 'package:flutter/material.dart';
import 'conversation_sidebar.dart';

/// Mobile drawer wrapper around [ConversationSidebar].
class ConversationDrawer extends StatelessWidget {
  const ConversationDrawer({super.key});

  @override
  Widget build(BuildContext context) {
    return ConversationSidebar(
      asDrawer: true,
      onClose: () => Navigator.pop(context),
    );
  }
}
