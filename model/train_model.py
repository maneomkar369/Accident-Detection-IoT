import numpy as np
import os
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

# Constants
WINDOW_SIZE = 100 # 1 second at 100Hz
FEATURES = 6      # ax, ay, az, gx, gy, gz
NUM_SAMPLES = 1000 # 500 crash, 500 non-crash

def generate_synthetic_data(num_samples=1000):
    X = []
    y = []
    
    for i in range(num_samples):
        is_crash = i < (num_samples // 2)
        sample = np.zeros((WINDOW_SIZE, FEATURES))
        
        if is_crash:
            # Impact point
            impact_idx = np.random.randint(20, 50)
            # High G spike
            sample[impact_idx:impact_idx+5, 0:3] = np.random.uniform(5, 10, (5, 3)) 
            # High rotation
            sample[impact_idx:impact_idx+5, 3:6] = np.random.uniform(200, 500, (5, 3))
            # Deceleration / Noise after impact
            sample[impact_idx+5:, :] = np.random.normal(0, 2, (WINDOW_SIZE - impact_idx - 5, FEATURES))
            label = 1
        else:
            # Normal driving noise
            sample = np.random.normal(0, 0.5, (WINDOW_SIZE, FEATURES))
            # Occasional bumps
            if np.random.random() > 0.7:
                bump_idx = np.random.randint(10, 80)
                sample[bump_idx:bump_idx+3, 0:3] = np.random.uniform(1, 3, (3, 3))
            label = 0
            
        X.append(sample)
        y.append(label)
        
    return np.array(X), np.array(y)

def extract_features(X):
    # For Random Forest, we need to flatten or extract statistical features
    # Let's extract: mean, std, max, min, energy for each axis
    features = []
    for sample in X:
        feat = []
        for i in range(FEATURES):
            axis_data = sample[:, i]
            feat.extend([
                np.mean(axis_data),
                np.std(axis_data),
                np.max(axis_data),
                np.min(axis_data),
                np.sum(axis_data**2) # Energy
            ])
        features.append(feat)
    return np.array(features)

def main():
    print("Generating synthetic data...")
    X_raw, y = generate_synthetic_data(NUM_SAMPLES)
    
    print("Extracting features...")
    X = extract_features(X_raw)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training Random Forest model...")
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    
    y_pred = clf.predict(X_test)
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Save the model
    os.makedirs('model', exist_ok=True)
    with open('model/crash_model.pkl', 'wb') as f:
        pickle.dump(clf, f)
    print("Model saved to model/crash_model.pkl")

if __name__ == "__main__":
    main()
