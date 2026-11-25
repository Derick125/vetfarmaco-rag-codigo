import 'package:app/core/error/failures.dart';
import 'package:app/features/onboarding/domain/repositories/onboarding_repository.dart';
import 'package:fpdart/fpdart.dart';
import 'package:hive_ce/hive_ce.dart';

/// Nome da caixa `hive_ce` própria da introdução de primeiro uso.
const nomeCaixaOnboarding = 'onboarding';

/// Chave que guarda a marca de introdução vista.
const chaveIntroducaoVista = 'introducao_vista';

/// Implementação de [OnboardingRepository] sobre a caixa `onboarding`.
///
/// Não guarda nenhum dado pessoal: só um booleano.
class OnboardingRepositoryImpl implements OnboardingRepository {
  /// Cria o repositório a partir da caixa `hive_ce` do módulo.
  const new(this._caixa);

  final Box<dynamic> _caixa;

  @override
  Future<Either<Failure, bool>> introducaoVista() async {
    try {
      return Right(_caixa.get(chaveIntroducaoVista) == true);
    } on Object {
      return const Left(FalhaCache('Não foi possível ler a introdução.'));
    }
  }

  @override
  Future<Either<Failure, Unit>> marcarIntroducaoVista() async {
    try {
      await _caixa.put(chaveIntroducaoVista, true);
      return const Right(unit);
    } on Object {
      return const Left(FalhaCache('Não foi possível gravar a introdução.'));
    }
  }
}
