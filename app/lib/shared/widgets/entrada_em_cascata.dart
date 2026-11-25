import 'dart:async';

import 'package:flutter/material.dart';

/// Entrada de um item de lista em cascata: *fade* e deslize, com [intervalo]
/// por posição (`docs/FRONTEND_SPEC.md` §25).
///
/// Só os primeiros [limite] itens entram escalonados; os demais aparecem de
/// uma vez. Cada item anima uma única vez (a chave do item mantém o estado
/// quando a lista é reconstruída). Com `MediaQuery.disableAnimations`, todos
/// aparecem de imediato. É só visual: o conteúdo já está na árvore.
class EntradaEmCascata extends StatefulWidget {
  /// Cria a entrada de [child] na posição [indice] da lista.
  const new({
    required this.indice,
    required this.child,
    this.intervalo = const Duration(milliseconds: 40),
    this.limite = 8,
    super.key,
  });

  /// Posição do item na lista.
  final int indice;

  /// Item exibido.
  final Widget child;

  /// Atraso entre itens consecutivos.
  final Duration intervalo;

  /// Quantidade máxima de itens escalonados.
  final int limite;

  @override
  State<EntradaEmCascata> createState() => _EntradaEmCascataState();
}

class _EntradaEmCascataState extends State<EntradaEmCascata> {
  Timer? _atraso;
  bool _visivel = false;
  bool _iniciado = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_iniciado) return;
    _iniciado = true;
    if (MediaQuery.disableAnimationsOf(context) ||
        widget.indice >= widget.limite) {
      _visivel = true;
      return;
    }
    _atraso = Timer(widget.intervalo * widget.indice, () {
      if (mounted) setState(() => _visivel = true);
    });
  }

  @override
  void dispose() {
    _atraso?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final semAnimacao = MediaQuery.disableAnimationsOf(context);
    final duracao = semAnimacao
        ? Duration.zero
        : const Duration(milliseconds: 180);
    return AnimatedOpacity(
      opacity: _visivel ? 1 : 0,
      duration: duracao,
      curve: Curves.easeOut,
      child: AnimatedSlide(
        offset: _visivel ? Offset.zero : const Offset(0, 0.15),
        duration: duracao,
        curve: Curves.easeOut,
        child: widget.child,
      ),
    );
  }
}
