import 'package:app/core/error/failures.dart';
import 'package:app/core/network/dio_failure_mapper.dart';
import 'package:app/features/ajustes/domain/repositories/ajustes_repository.dart';
import 'package:app/features/ajustes/domain/saude_backend.dart';
import 'package:app/features/bootstrap/data/repositories/configuracao_repository_impl.dart';
import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:dio/dio.dart';
import 'package:fpdart/fpdart.dart';
import 'package:hive_ce/hive_ce.dart';
import 'package:injectable/injectable.dart';

/// Chave da condição de rede da campanha (telemetria).
const chaveCondicaoCampanha = 'condicaoCampanha';

/// Chave do último modelo informado por `GET /health`.
const chaveUltimoModelo = 'ultimoModelo';

/// Implementação de [AjustesRepository]: `hive_ce` + `dio`.
@LazySingleton(as: AjustesRepository)
class AjustesRepositoryImpl implements AjustesRepository {
  /// Cria o repositório.
  const new(this._caixa, this._dio);

  final Box<dynamic> _caixa;
  final Dio _dio;

  @override
  Future<Either<Failure, Unit>> salvarEndereco(String endereco) async {
    try {
      await _caixa.put(chaveEnderecoBackend, endereco);
      return const Right(unit);
    } on Object {
      return const Left(FalhaCache('Não foi possível gravar o endereço.'));
    }
  }

  @override
  Future<Either<Failure, Unit>> testarBackend(String endereco) async =>
      (await consultarSaude(endereco)).map((_) => unit);

  @override
  Future<Either<Failure, SaudeBackend>> consultarSaude(String endereco) async {
    try {
      final r = await _dio.get<dynamic>('$endereco/health');
      final status = r.statusCode;
      if (status == null || status < 200 || status >= 300) {
        return Left(falhaDeStatus(status));
      }
      final dados = r.data;
      final modelo = dados is Map<String, dynamic> ? dados['modelo_id'] : null;
      if (modelo is String) {
        try {
          await _caixa.put(chaveUltimoModelo, modelo);
        } on Object {
          // Guardar o último modelo é auxiliar: não derruba o /health.
        }
      }
      return Right(SaudeBackend(modeloId: modelo is String ? modelo : null));
    } on DioException catch (e) {
      return Left(falhaDeDio(e));
    }
  }

  @override
  Future<String?> ultimoModeloConhecido() async {
    try {
      return _caixa.get(chaveUltimoModelo) as String?;
    } on Object {
      return null;
    }
  }

  @override
  Future<CondicaoCampanha> condicaoCampanha() async {
    try {
      return CondicaoCampanha.dePorNome(
        _caixa.get(chaveCondicaoCampanha) as String?,
      );
    } on Object {
      return CondicaoCampanha.naoInformada;
    }
  }

  @override
  Future<Either<Failure, Unit>> salvarCondicaoCampanha(
    CondicaoCampanha condicao,
  ) async {
    try {
      await _caixa.put(chaveCondicaoCampanha, condicao.name);
      return const Right(unit);
    } on Object {
      return const Left(FalhaCache('Não foi possível gravar a condição.'));
    }
  }
}
