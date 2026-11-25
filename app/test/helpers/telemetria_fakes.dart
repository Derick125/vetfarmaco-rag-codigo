import 'package:app/core/error/failures.dart';
import 'package:app/features/historico/domain/repositories/resposta_cache_repository.dart';
import 'package:app/features/historico/domain/resposta_salva.dart';
import 'package:app/features/historico/domain/usecases/buscar_resposta_salva.dart';
import 'package:app/features/historico/domain/usecases/salvar_resposta.dart';
import 'package:app/features/resposta/domain/usecases/realizar_consulta.dart';
import 'package:app/features/resposta/presentation/cubit/resposta_cubit.dart';
import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:app/features/telemetria/domain/contexto_medicao.dart';
import 'package:app/features/telemetria/domain/registro_telemetria.dart';
import 'package:app/features/telemetria/domain/repositories/telemetria_repository.dart';
import 'package:app/features/telemetria/domain/usecases/capturar_contexto_medicao.dart';
import 'package:app/features/telemetria/domain/usecases/registrar_telemetria.dart';
import 'package:fpdart/fpdart.dart';

/// Repositório em memória.
class TelemetriaEmMemoria implements TelemetriaRepository {
  /// Registros gravados.
  final registros = <RegistroTelemetria>[];

  @override
  Future<Either<Failure, Unit>> gravar(RegistroTelemetria registro) async {
    registros.add(registro);
    return const Right(unit);
  }

  @override
  Future<Either<Failure, List<RegistroTelemetria>>> listar() async =>
      Right(List.of(registros));
}

/// Caso de uso que guarda os registros em memória.
class RegistrarFalso extends RegistrarTelemetria {
  /// Cria o falso sobre [memoria].
  new([TelemetriaEmMemoria? memoria])
    : memoria = memoria ?? TelemetriaEmMemoria(),
      super(memoria ?? TelemetriaEmMemoria());

  /// Onde os registros caem.
  final TelemetriaEmMemoria memoria;

  @override
  Future<Either<Failure, Unit>> call(RegistroTelemetria registro) =>
      memoria.gravar(registro);
}

/// Rede fixa.
class RedeFalsa implements CondicaoRede {
  /// Cria a rede com [rotulo].
  const new([this.rotulo = 'wifi']);

  /// Valor devolvido.
  final String rotulo;

  @override
  Future<String> atual() async => rotulo;
}

/// Cache de respostas em memória.
class CacheEmMemoria implements RespostaCacheRepository {
  /// Respostas guardadas por chave.
  final guardadas = <String, RespostaSalva>{};

  @override
  Future<Either<Failure, Unit>> salvar(RespostaSalva resposta) async {
    guardadas[resposta.chave] = resposta;
    return const Right(unit);
  }

  @override
  Future<Either<Failure, RespostaSalva?>> buscar(String chave) async =>
      Right(guardadas[chave]);

  @override
  Future<Either<Failure, List<RespostaSalva>>> historico() async => Right(
    guardadas.values.toList()..sort((a, b) => b.geradaEm.compareTo(a.geradaEm)),
  );

  @override
  Future<Either<Failure, Unit>> remover(String chave) async {
    guardadas.remove(chave);
    return const Right(unit);
  }
}

/// Cubit de resposta com telemetria e cache em memória.
RespostaCubit novoRespostaCubit(
  RealizarConsulta realizar, {
  TelemetriaEmMemoria? telemetria,
  CacheEmMemoria? cache,
  String rede = 'wifi',
  CondicaoCampanha condicao = CondicaoCampanha.naoInformada,
  String? modelo,
}) {
  final c = cache ?? CacheEmMemoria();
  return RespostaCubit(
    realizar,
    RegistrarFalso(telemetria),
    ContextoFalso(
      ContextoMedicao(rede: rede, condicao: condicao, modelo: modelo),
    ),
    SalvarResposta(c),
    BuscarRespostaSalva(c),
  );
}

/// Contexto de medição fixo (sem rede, sem `/health`).
class ContextoFalso implements CapturarContextoMedicao {
  /// Cria o contexto.
  const new(this.contexto);

  /// Valor devolvido.
  final ContextoMedicao contexto;

  @override
  Future<ContextoMedicao> call() async => contexto;
}
