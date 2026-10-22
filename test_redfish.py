import time
import subprocess
import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BMC_IP = "localhost"
BMC_PORT = "2443"
USER = "root"
PASSWORD = "0penBmc"
IPMI_PORT = "2623"

BASE_URL = f"https://{BMC_IP}:{BMC_PORT}/redfish/v1"

@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.verify = False
    s.auth = (USER, PASSWORD)
    return s

def test_auth(session):
    url = f"{BASE_URL}/SessionService/Sessions"
    body = {"UserName": USER, "Password": PASSWORD}
    response = session.post(url, json=body)
    assert response.status_code in (200, 201), f"Ожидался 200/201, получен {response.status_code}"
    assert "X-Auth-Token" in response.headers, "Токен сессии не найден в заголовках"
    print(f"\nOK: auth, token len={len(response.headers['X-Auth-Token'])}")

def test_get_system_info(session):
    url = f"{BASE_URL}/Systems/system"
    response = session.get(url)
    assert response.status_code == 200, f"Ожидался 200, получен {response.status_code}"
    data = response.json()
    assert "Status" in data, "В ответе отсутствует поле Status"
    assert "PowerState" in data, "В ответе отсутствует поле PowerState"
    print(f"\nOK: system, PowerState={data['PowerState']}")

def test_power_on(session):
    url = f"{BASE_URL}/Systems/system/Actions/ComputerSystem.Reset"
    body = {"ResetType": "On"}
    response = session.post(url, json=body)
    assert response.status_code in (202, 204), f"Ожидался 202 или 204, получен {response.status_code}"
    print("\nOK: power on отправлен (202/204)")
    time.sleep(5)
    sys_url = f"{BASE_URL}/Systems/system"
    s = session.get(sys_url)
    assert s.status_code == 200
    power_state = s.json().get("PowerState")
    valid_states = ("On", "Off", "PoweringOn", "PoweringOff")
    assert power_state in valid_states, f"PowerState={power_state} не входит в допустимые"
    print(f"OK: PowerState={power_state} (валидное состояние)")

def test_thermal_metrics(session):
    url = f"{BASE_URL}/Chassis/chassis/ThermalSubsystem/ThermalMetrics"
    response = session.get(url)
    assert response.status_code == 200, f"Ожидался 200, получен {response.status_code}"
    data = response.json()
    assert "TemperatureReadingsCelsius" in data, "Нет поля TemperatureReadingsCelsius"
    assert isinstance(data["TemperatureReadingsCelsius"], list), "Поле не является списком"
    print(f"\nOK: ThermalMetrics получен. Датчиков в Redfish: {len(data['TemperatureReadingsCelsius'])}")

def test_ipmi_vs_redfish():
    cmd = ["ipmitool", "-I", "lanplus", "-H", BMC_IP, "-p", IPMI_PORT, "-U", USER, "-P", PASSWORD, "sensor", "list"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout
    except Exception as e:
        pytest.fail(f"Ошибка вызова ipmitool: {e}")

    assert "p0_core0_temp" in output, "Не найден датчик p0_core0_temp в IPMI"
    assert "p1_core0_temp" in output, "Не найден датчик p1_core0_temp в IPMI"
    print("\nOK: IPMI возвращает датчики температуры CPU (p0_core0_temp, p1_core0_temp)")
