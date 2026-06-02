import hashlib
import random
import ecdsa
import base58
import time
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from sympy import mod_inverse
from scipy.stats import norm
from multiprocessing import Pool

# 🔹 Ustawienia
n = ecdsa.SECP256k1.order
G = ecdsa.SECP256k1.generator
target_address = "1D2B7zfX6HgnuG7bMT1znFMsGdqX97Fnon"

# 🔹 Lista transakcji do testowania
transactions = [
    {"r": 0x42af7b84c7e3aed62c5e727bc8688d5bcdd97058b41c57e6526b0e1794d951ba,
     "s": 0x383b722470466437e13186a1f7b19053d17568e94ad869cea9aaaf5de63be539,
     "z": 0x81df111086a02e6ec546aee887965fabf4418f6dc2d246286ff70280452b7eaa},

    {"r": 0x4204e1db3eba462403eaecfc5863200f1013600f2bc58eafa91d7d5431eb810b,
     "s": 0x68f422d92cfdf6f961a421c115df52c212e2c264bebd21332fb27797483e9f84,
     "z": 0xf3196693e7514fe9195e65cd49c11bb84f81e61a60fc73db12c5f6d19f05f329},
]

# 🔹 Przechowywanie historycznych wartości `k`
historical_k = []

# 🔹 Konwersja kluczy
def private_key_to_public_key(private_key):
    point = private_key * G
    public_key = b'\x04' + point.x().to_bytes(32, 'big') + point.y().to_bytes(32, 'big')
    return public_key

def public_key_to_bitcoin_address(public_key):
    sha256 = hashlib.sha256(public_key).digest()
    ripemd160 = hashlib.new('ripemd160', sha256).digest()
    prefixed_key = b'\x00' + ripemd160
    checksum = hashlib.sha256(hashlib.sha256(prefixed_key).digest()).digest()[:4]
    address_bytes = prefixed_key + checksum
    return base58.b58encode(address_bytes).decode('utf-8')

# 🔹 Odzyskiwanie `d` przy znanym `k`
def recover_private_key(r, s, z, k, n):
    k_inv = mod_inverse(k, n)
    d = ((s * k) - z) * mod_inverse(r, n) % n
    return d

# 🔹 Model probabilistyczny (przewidywanie `k` na podstawie rozkładu)
def predict_k_probabilistic(k_values):
    mean, std = norm.fit(k_values)
    return int(np.random.normal(mean, std)) % n  # Losujemy `k` zgodnie z rozkładem

# 🔹 Tworzenie modelu LSTM
def create_lstm_model():
    model = Sequential([
        LSTM(50, activation='relu', return_sequences=True, input_shape=(5, 1)),
        LSTM(50, activation='relu'),
        Dense(1)
    ])
    model.compile(optimizer='adam', loss='mse')
    return model

# 🔹 Trenowanie LSTM
def train_lstm_model(k_values):
    if len(k_values) < 10:
        return None

    X, y = [], []
    for i in range(len(k_values) - 5):
        X.append(k_values[i:i+5])
        y.append(k_values[i+5])

    X, y = np.array(X, dtype=object), np.array(y, dtype=object)  # Use np.object to store large integers

    X = X.reshape((X.shape[0], X.shape[1], 1))  # Reshaping for LSTM

    model = create_lstm_model()
    model.fit(X, y, epochs=100, verbose=0)
    return model

# 🔹 Przewidywanie `k` przy użyciu AI
def ai_attack_k(historical_k):
    if len(historical_k) < 10:
        return None

    lstm_model = train_lstm_model(historical_k)
    lstm_pred = predict_k_lstm(lstm_model, historical_k) if lstm_model else None
    prob_pred = predict_k_probabilistic(historical_k)

    print(f"🧠 AI przewidywanie: LSTM={lstm_pred}, Probabilistyczny={prob_pred}")

    return lstm_pred if lstm_pred else prob_pred

# 🔹 Brute-force na `d`
def brute_force_d(r, s, z, n, max_attempts=500000):
    for attempt in range(max_attempts):
        k = ai_attack_k(historical_k) if random.random() < 0.5 else random.randint(1, n - 1)
        d = random.randint(1, n - 1)

        R_x = (k * G).x() % n
        if R_x == 0:
            continue

        k_inv = mod_inverse(k, n)
        s_calc = (k_inv * (z + d * R_x)) % n

        if s_calc == s:
            return d, k

        if attempt % 10000 == 0:
            print(f"🔄 Próba {attempt}: r={r}, s={s}, z={z}, k={k}, d={d}")

    return None, None

# 🔹 Główne wykonanie programu
if __name__ == "__main__":
    print("🚀 Rozpoczynamy atak...")

    for tx in transactions:
        r, s, z = tx["r"], tx["s"], tx["z"]
        print(f"\n🔍 Analiza transakcji: r={r}, s={s}, z={z}")

        for _ in range(20):  
            historical_k.append(random.randint(1, n - 1))

        print("🚀 Uruchamianie AI + brute-force...")
        d, k = brute_force_d(r, s, z, n)

        if d:
            elapsed_time = time.time() - start_time
            print(f"🎯 Znaleziono klucz: d = {d}, k = {k} w czasie {elapsed_time:.2f} sekund")
            with open("found_keys.txt", "a", encoding="utf-8") as file:
                file.write(f"🎯 Transakcja: r={r}, s={s}, z={z}\n")
                file.write(f"🔹 Znaleziono d: {d}, k: {k}\n")
                file.write(f"--------------------------------------------------\n")
            break
        else:
            print("❌ Nie udało się odzyskać klucza. Możliwe przyczyny:")
            print("   - `k` jest poprawnie generowane (RFC 6979) i nie da się go przewidzieć.")
            print("   - Za mało prób brute-force.")
            print("   - AI nie znalazło wzorca w `k`.")

print("✅ Proces zakończony.")
