import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/room_upgrade.dart';
import '../theme/app_theme.dart';

class ShoppingCard extends StatelessWidget {
  final SelectedProduct selectedProduct;
  final bool compact;

  const ShoppingCard({
    super.key,
    required this.selectedProduct,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    final product = selectedProduct.chosenProduct;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppTheme.border),
        boxShadow: AppTheme.cardShadow,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(14),
            child: CachedNetworkImage(
              imageUrl: product.imageUrl,
              width: compact ? 72 : 92,
              height: compact ? 72 : 92,
              fit: BoxFit.cover,
              errorWidget: (_, _, _) => _imageFallback(),
              placeholder: (_, _) => _imageFallback(),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    _StoreBadge(store: product.store),
                    const Spacer(),
                    Text(
                      '\$${product.price.toStringAsFixed(2)}',
                      style: GoogleFonts.dmSans(
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  product.title,
                  maxLines: compact ? 2 : 3,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.dmSans(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                    height: 1.25,
                  ),
                ),
                if (selectedProduct.reasoning != null) ...[
                  const SizedBox(height: 6),
                  Text(
                    selectedProduct.reasoning!,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.dmSans(
                      fontSize: 12,
                      color: AppTheme.textMuted,
                    ),
                  ),
                ],
                const SizedBox(height: 10),
                Row(
                  children: [
                    if (product.rating != null) _Rating(value: product.rating!),
                    const Spacer(),
                    TextButton(
                      onPressed: () => _openBuyLink(context, product.buyLink),
                      child: Text('Buy on ${product.store}'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _imageFallback() {
    return Container(
      width: compact ? 72 : 92,
      height: compact ? 72 : 92,
      color: AppTheme.inputBackground,
      child: const Icon(Icons.chair_outlined, color: AppTheme.textMuted),
    );
  }

  Future<void> _openBuyLink(BuildContext context, String link) async {
    final uri = Uri.tryParse(link);
    if (uri == null) return;

    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open product link.')),
      );
    }
  }
}

class _StoreBadge extends StatelessWidget {
  final String store;

  const _StoreBadge({required this.store});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppTheme.primaryColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        store,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: GoogleFonts.dmSans(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: AppTheme.primaryDark,
        ),
      ),
    );
  }
}

class _Rating extends StatelessWidget {
  final double value;

  const _Rating({required this.value});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.star_rounded, size: 16, color: AppTheme.warning),
        const SizedBox(width: 2),
        Text(
          value.toStringAsFixed(1),
          style: GoogleFonts.dmSans(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            color: AppTheme.textSecondary,
          ),
        ),
      ],
    );
  }
}
