"""Optional path choices for moved/nonstandard installations."""
import paths


def main():
    print('1. Remnants Setup 파일 위치')
    print('2. 좀보이드 사용자 데이터 폴더 (보통 사용자 폴더의 Zomboid)')
    print('0. 취소')
    option = input('변경할 위치 번호: ').strip()
    choices = {'1':('setup_path', False), '2':('zomboid_path', True)}
    if option not in choices:
        return
    key, directory = choices[option]
    path = paths.pick_path('사용할 파일 또는 폴더를 선택하세요.', directory=directory)
    if key == 'setup_path' and path.name.lower() != 'projectremnantssetup.exe':
        raise ValueError('ProjectRemnantsSetup.exe를 선택해주세요.')
    paths.remember(key, path)
    print('저장했습니다. 실행 중인 변환기를 종료한 뒤 다시 실행하면 적용됩니다.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print(str(error))
        raise SystemExit(1)
