import 'dart:convert';

import 'package:app/core/error/failures.dart';
import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:app/features/telemetria/domain/registro_telemetria.dart';
import 'package:app/features/telemetria/domain/repositories/telemetria_repository.dart';
import 'package:fpdart/fpdart.dart';
import 'package:hive_ce/hive_ce.dart';
import 'package:injectable/injectable.dart';

/// Nome da caixa `hive_ce` das medições.
const nomeCaixaTelemetria = 'telemetria';

/// Registro como mapa JSON (chaves estáveis, para ler dados antigos).
Map<String, Object?> registroParaJson(RegistroTelemetria r) => {
  'consultaId': r.consultaId,
  'data': r.data.toUtc().toIso8601String(),
  'modelo': r.modelo,
  'thinkingLevel': r.thinkingLevel,
  'rede': r.rede,
  'condicaoCampanha': r.condicaoCampanha.name,
  'desfecho': r.desfecho.name,
  'nivelConfianca': r.nivelConfianca,
  'primeiroEventoMs': r.primeiroEventoMs,
  'ttftMs': r.ttftMs,
  'totalClienteMs': r.totalClienteMs,
  'primeiroTokenServidorMs': r.primeiroTokenServidorMs,
  'primeiroParagrafoValidadoServidorMs': r.primeiroParagrafoValidadoServidorMs,
  'totalServidorMs': r.totalServidorMs,
  'inputTokens': r.inputTokens,
  'outputTokens': r.outputTokens,
  'thoughtTokens': r.thoughtTokens,
  'custoUsd': r.custoUsd,
  'chunks': r.chunks,
  'paragrafos': r.paragrafos,
  'falha': r.falha,
};

/// Lê o mapa gravado por [registroParaJson]; lança em caso de dado corrompido.
RegistroTelemetria registroDeJson(Map<String, dynamic> j) {
  double? d(String k) => (j[k] as num?)?.toDouble();
  return RegistroTelemetria(
    consultaId: j['consultaId'] as String,
    data: DateTime.parse(j['data'] as String),
    modelo: j['modelo'] as String?,
    thinkingLevel: j['thinkingLevel'] as String?,
    rede: j['rede'] as String,
    condicaoCampanha: CondicaoCampanha.dePorNome(
      j['condicaoCampanha'] as String?,
    ),
    desfecho: DesfechoConsulta.values.byName(j['desfecho'] as String),
    nivelConfianca: j['nivelConfianca'] as String?,
    primeiroEventoMs: j['primeiroEventoMs'] as int?,
    ttftMs: j['ttftMs'] as int?,
    totalClienteMs: j['totalClienteMs'] as int,
    primeiroTokenServidorMs: d('primeiroTokenServidorMs'),
    primeiroParagrafoValidadoServidorMs: d(
      'primeiroParagrafoValidadoServidorMs',
    ),
    totalServidorMs: d('totalServidorMs'),
    inputTokens: j['inputTokens'] as int?,
    outputTokens: j['outputTokens'] as int?,
    thoughtTokens: j['thoughtTokens'] as int?,
    custoUsd: d('custoUsd'),
    chunks: j['chunks'] as int?,
    paragrafos: j['paragrafos'] as int,
    falha: j['falha'] as String?,
  );
}

/// [TelemetriaRepository] sobre uma caixa `hive_ce`.
@LazySingleton(as: TelemetriaRepository)
class TelemetriaRepositoryImpl implements TelemetriaRepository {
  /// Cria o repositório.
  const new(@Named('telemetria') this._caixa);

  final Box<dynamic> _caixa;

  @override
  Future<Either<Failure, Unit>> gravar(RegistroTelemetria registro) async {
    try {
      await _caixa.put(
        registro.consultaId,
        jsonEncode(registroParaJson(registro)),
      );
      return const Right(unit);
    } on Object {
      return const Left(FalhaCache('Não foi possível gravar a telemetria.'));
    }
  }

  @override
  Future<Either<Failure, List<RegistroTelemetria>>> listar() async {
    try {
      final lista = [
        for (final bruto in _caixa.values)
          registroDeJson(jsonDecode(bruto as String) as Map<String, dynamic>),
      ]..sort((a, b) => a.data.compareTo(b.data));
      return Right(lista);
    } on Object {
      return const Left(FalhaCache('Não foi possível ler a telemetria.'));
    }
  }
}
