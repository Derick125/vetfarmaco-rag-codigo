import 'dart:async';

import 'package:app/core/error/failures.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/historico/domain/resposta_salva.dart';
import 'package:app/features/historico/domain/usecases/buscar_resposta_salva.dart';
import 'package:app/features/historico/domain/usecases/salvar_resposta.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/domain/usecases/realizar_consulta.dart';
import 'package:app/features/resposta/presentation/cubit/resposta_state.dart';
import 'package:app/features/telemetria/domain/contexto_medicao.dart';
import 'package:app/features/telemetria/domain/registro_telemetria.dart';
import 'package:app/features/telemetria/domain/ttft_stopwatch.dart';
import 'package:app/features/telemetria/domain/usecases/capturar_contexto_medicao.dart';
import 'package:app/features/telemetria/domain/usecases/registrar_telemetria.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:injectable/injectable.dart';

/// Controla `/consulta/:id`: consome o stream, acumula os eventos e grava a
/// telemetria da consulta.
@injectable
class RespostaCubit extends Cubit<RespostaState> {
  /// Cria o cubit.
  new(
    this._realizar,
    this._registrar,
    this._contexto,
    this._salvar,
    this._buscar,
  ) : super(const RespostaState());

  final RealizarConsulta _realizar;
  final RegistrarTelemetria _registrar;
  final CapturarContextoMedicao _contexto;
  final SalvarResposta _salvar;
  final BuscarRespostaSalva _buscar;
  late CorpoConsulta _corpo;
  StreamSubscription<dynamic>? _assinatura;

  /// Fábrica do cronômetro; os testes trocam por um relógio controlado.
  @visibleForTesting
  TtftStopwatch Function() criarRelogio = TtftStopwatch.new;

  /// Relógio da data de coleta; os testes trocam por um fixo.
  @visibleForTesting
  DateTime Function() agora = DateTime.now;

  late TtftStopwatch _relogio;
  late String _consultaId;
  late Future<ContextoMedicao> _contextoAoEnviar;
  var _paragrafosRecebidos = 0;
  int? _chunks;
  String? _thinkingLevel;
  var _gravado = false;

  /// Envia [corpo] e acompanha a resposta. Reenvia do zero se já iniciou.
  Future<void> iniciar(CorpoConsulta corpo) async {
    await _assinatura?.cancel();
    _corpo = corpo;
    emit(const RespostaState());
    _consultaId = agora().microsecondsSinceEpoch.toString();
    _paragrafosRecebidos = 0;
    _chunks = null;
    _thinkingLevel = null;
    _gravado = false;
    // Em paralelo ao envio: não atrasa a consulta.
    _contextoAoEnviar = _contexto();
    _relogio = criarRelogio()..iniciar();
    _assinatura = _realizar(corpo).listen((r) {
      r.match(_aoFalhar, _aoEvento);
    });
  }

  void _aoEvento(EventoResposta e) {
    _relogio.registrar(e);
    switch (e) {
      case EventoRecuperacao(:final chunks, :final thinkingLevel):
        _chunks = chunks;
        _thinkingLevel = thinkingLevel;
        emit(state.copiar(chunks: chunks));
      case EventoParagrafo():
        _paragrafosRecebidos++;
        emit(
          state.copiar(
            fase: FaseResposta.transmitindo,
            paragrafos: [...state.paragrafos, e],
          ),
        );
      case EventoCitacoes(:final citacoes):
        emit(state.copiar(citacoes: citacoes));
      case EventoAlerta():
        emit(state.copiar(alerta: e));
      case EventoFim():
        final semEvidencia = e.nivelConfianca == NivelConfianca.semEvidencia;
        emit(
          semEvidencia
              // Sem evidência é sucesso: nada de parágrafo como resposta.
              ? RespostaState(
                  fase: FaseResposta.semEvidencia,
                  chunks: state.chunks,
                  fim: e,
                  geradaEm: agora(),
                )
              : state.copiar(
                  fase: FaseResposta.concluida,
                  fim: e,
                  geradaEm: agora(),
                ),
        );
        unawaited(
          _gravar(
            semEvidencia
                ? DesfechoConsulta.semEvidencia
                : DesfechoConsulta.concluida,
            fim: e,
          ),
        );
    }
  }

  void _aoFalhar(Failure f) {
    // Falha de transporte mantém o texto já exibido, marcado como parcial;
    // qualquer outra (citação fantasma, contrato, servidor) invalida tudo
    // (`docs/ARCHITECTURE.md` §4).
    final transporte = f is FalhaTempo || f is FalhaRede;
    if (transporte && state.paragrafos.isEmpty) {
      unawaited(_tentarCache(f));
      return;
    }
    final parcial = transporte;
    if (parcial) {
      emit(
        state.copiar(
          fase: FaseResposta.falha,
          mensagem: f.mensagem,
          incompleta: true,
        ),
      );
    } else {
      emit(RespostaState(fase: FaseResposta.falha, mensagem: f.mensagem));
    }
    unawaited(
      _gravar(
        parcial ? DesfechoConsulta.incompleta : DesfechoConsulta.falha,
        falha: f.runtimeType.toString(),
      ),
    );
  }

  /// Sem rede e sem nada recebido: serve a resposta guardada desta consulta,
  /// com o selo de data; sem ela, o estado `Offline sem cache`.
  Future<void> _tentarCache(Failure f) async {
    final r = await _buscar(_corpo);
    final guardada = r.toNullable();
    if (isClosed) return;
    if (guardada != null) {
      _exibir(guardada);
      // O modelo e o nível são os de quem gerou a resposta guardada.
      unawaited(
        _gravar(
          DesfechoConsulta.cache,
          modelo: guardada.fim.modelo,
          thinkingLevel: guardada.fim.thinkingLevel,
        ),
      );
      return;
    }
    emit(
      RespostaState(
        fase: f is FalhaRede
            ? FaseResposta.offlineSemCache
            : FaseResposta.falha,
        mensagem: f.mensagem,
      ),
    );
    unawaited(_gravar(DesfechoConsulta.falha, falha: f.runtimeType.toString()));
  }

  /// Mostra uma resposta guardada (histórico), sem consultar o servidor.
  Future<void> exibirSalva(RespostaSalva salva) async {
    await _assinatura?.cancel();
    _corpo = salva.corpo;
    _exibir(salva);
  }

  void _exibir(RespostaSalva s) => emit(
    RespostaState(
      fase: s.fim.nivelConfianca == NivelConfianca.semEvidencia
          ? FaseResposta.semEvidencia
          : FaseResposta.concluida,
      paragrafos: s.paragrafos,
      citacoes: s.citacoes,
      alerta: s.alerta,
      fim: s.fim,
      geradaEm: s.geradaEm,
      origemCache: true,
      salva: true,
    ),
  );

  /// Guarda a resposta atual no histórico.
  Future<void> salvar() async {
    final fim = state.fim;
    if (state.fase != FaseResposta.concluida ||
        fim == null ||
        state.origemCache ||
        state.salva) {
      return;
    }
    final r = await _salvar(
      RespostaSalva(
        corpo: _corpo,
        paragrafos: state.paragrafos,
        citacoes: state.citacoes,
        alerta: state.alerta,
        fim: fim,
        geradaEm: state.geradaEm ?? agora(),
      ),
    );
    if (isClosed) return;
    r.match(
      (f) => emit(state.copiar(mensagem: f.mensagem)),
      (_) => emit(state.copiar(salva: true)),
    );
  }

  /// Grava as medições uma vez por consulta; falha ao gravar não afeta a
  /// resposta exibida.
  Future<void> _gravar(
    DesfechoConsulta desfecho, {
    EventoFim? fim,
    String? falha,
    String? modelo,
    String? thinkingLevel,
  }) async {
    if (_gravado) return;
    _gravado = true;
    final t = fim?.tempos;
    final contexto = await _contextoAoEnviar;
    final registro = RegistroTelemetria(
      consultaId: _consultaId,
      data: agora(),
      // O `fim` é a fonte do modelo que gerou a resposta; sem ele (falha
      // antes do fim), vale o informado por /health no envio.
      modelo: fim?.modelo ?? modelo ?? contexto.modelo,
      thinkingLevel: fim?.thinkingLevel ?? thinkingLevel ?? _thinkingLevel,
      rede: contexto.rede,
      condicaoCampanha: contexto.condicao,
      desfecho: desfecho,
      nivelConfianca: fim?.nivelConfianca.name,
      primeiroEventoMs: _relogio.primeiroEventoMs,
      ttftMs: _relogio.ttftMs,
      totalClienteMs: _relogio.totalMs,
      primeiroTokenServidorMs: t?.primeiroToken,
      primeiroParagrafoValidadoServidorMs: t?.primeiroParagrafoValidado,
      totalServidorMs: t?.total,
      inputTokens: fim?.inputTokens,
      outputTokens: fim?.outputTokens,
      thoughtTokens: fim?.thoughtTokens,
      custoUsd: fim?.custoUsd,
      chunks: _chunks,
      paragrafos: _paragrafosRecebidos,
      falha: falha,
    );
    await _registrar(registro);
  }

  @override
  Future<void> close() async {
    await _assinatura?.cancel();
    return await super.close();
  }
}
