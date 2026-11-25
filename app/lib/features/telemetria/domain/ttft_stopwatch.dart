import 'package:app/features/resposta/domain/evento_resposta.dart';

/// Cronômetro do contrato de TTFT (`docs/FRONTEND_SPEC.md` §6).
///
/// Mede do envio da requisição até o **primeiro parágrafo validado** com
/// texto (`ttftMs`), separado do tempo até o primeiro evento do stream
/// (`primeiroEventoMs`). O primeiro token do modelo só existe no servidor.
class TtftStopwatch {
  /// Cria o cronômetro; [agoraMs] existe para os testes controlarem o tempo.
  new({int Function()? agoraMs}) : _agoraMs = agoraMs ?? _relogioReal();

  final int Function() _agoraMs;
  int _inicio = 0;

  /// Ms até o primeiro evento do stream (`recuperacao`).
  int? primeiroEventoMs;

  /// Ms até o primeiro parágrafo validado com texto: o TTFT do contrato.
  int? ttftMs;

  /// Começa a contar, no envio da requisição.
  void iniciar() {
    _inicio = _agoraMs();
    primeiroEventoMs = null;
    ttftMs = null;
  }

  /// Registra a chegada de [evento].
  void registrar(EventoResposta evento) {
    final t = _agoraMs() - _inicio;
    primeiroEventoMs ??= t;
    if (evento is EventoParagrafo && evento.texto.trim().isNotEmpty) {
      ttftMs ??= t;
    }
  }

  /// Ms desde o envio.
  int get totalMs => _agoraMs() - _inicio;
}

int Function() _relogioReal() {
  final s = Stopwatch()..start();
  return () => s.elapsedMilliseconds;
}
