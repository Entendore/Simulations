import simpy
import random
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from threading import Thread, Lock
from collections import deque, Counter
import time
import csv

# Constants
RANDOM_SEED = 42
SIM_DURATION = 120  # minutes
REALTIME_SPEED = 0.15  # seconds per simulated minute

# Patient types and their attributes
PATIENT_TYPES = {
    'Critical': {'priority': 0, 'treat_time': 15, 'needs_xray': True, 'needs_surgery': True},
    'Moderate': {'priority': 1, 'treat_time': 10, 'needs_xray': True, 'needs_surgery': False},
    'Mild':     {'priority': 2, 'treat_time': 5,  'needs_xray': False, 'needs_surgery': False}
}

# Globals for plotting and stats
times = deque(maxlen=300)
patients_in_system = deque(maxlen=300)
waiting_queue = deque(maxlen=300)
patient_type_count = deque(maxlen=300)

# Shared state variables
current_patients = [0]
current_waiting = [0]
type_counter = Counter()
stats_lock = Lock()

# For logging patient stats to CSV
patient_logs = []
csv_file = 'patient_stats.csv'

# Staffing shifts schedule (time in minutes -> number of doctors)
# Example: 0-60: 2 doctors; 60-120: 1 doctor (night shift)
STAFF_SCHEDULE = [
    (0, 2),    # from 0 min to <60 min: 2 doctors
    (60, 1),   # from 60 min onward: 1 doctor
]

def get_doctors_capacity(current_time):
    # Return doctors count based on schedule
    for start_time, doctors_count in reversed(STAFF_SCHEDULE):
        if current_time >= start_time:
            return doctors_count
    return STAFF_SCHEDULE[0][1]  # default to first if no match

# Patient process
def patient(env, name, doctors, xray, surgery):
    ptype = random.choices(
        population=list(PATIENT_TYPES.keys()),
        weights=[1, 2, 4]
    )[0]
    data = PATIENT_TYPES[ptype]
    priority = data['priority']
    arrival = env.now

    with stats_lock:
        current_patients[0] += 1
        type_counter[ptype] += 1

    # Triage delay (fixed small delay)
    yield env.timeout(random.uniform(1, 2))

    # Request doctor with priority
    with doctors.request(priority=priority) as req:
        with stats_lock:
            current_waiting[0] += 1
        yield req
        with stats_lock:
            current_waiting[0] -= 1
        # Treatment time by doctor
        yield env.timeout(data['treat_time'])

    # X-Ray if needed
    if data['needs_xray']:
        with xray.request() as req:
            yield req
            yield env.timeout(random.uniform(5, 8))

    # Surgery if needed
    if data['needs_surgery']:
        with surgery.request() as req:
            yield req
            yield env.timeout(random.uniform(10, 15))

    # Discharge (instant for simplicity)
    with stats_lock:
        current_patients[0] -= 1
        type_counter[ptype] -= 1

    # Log patient info
    total_time = env.now - arrival
    wait_time = total_time - data['treat_time']
    patient_logs.append({
        'Name': name,
        'Type': ptype,
        'Arrival': round(arrival,2),
        'Departure': round(env.now,2),
        'WaitTime': round(wait_time,2),
        'TotalTime': round(total_time,2)
    })

# Patient arrival generator
def patient_generator(env, doctors_ref, xray, surgery):
    i = 0
    while True:
        yield env.timeout(random.uniform(1, 3))
        i += 1
        env.process(patient(env, f'Patient {i}', doctors_ref, xray, surgery))

# Manage dynamic doctor capacity (shift changes)
def manage_doctors(env, doctors):
    while True:
        current_capacity = get_doctors_capacity(env.now)
        if doctors.capacity != current_capacity:
            doctors.capacity = current_capacity
        yield env.timeout(1)  # check every simulated minute

# Run simulation and collect stats
def run_simulation():
    random.seed(RANDOM_SEED)
    env = simpy.Environment()

    doctors = simpy.PriorityResource(env, capacity=STAFF_SCHEDULE[0][1])
    xray = simpy.Resource(env, capacity=1)
    surgery = simpy.Resource(env, capacity=1)

    env.process(patient_generator(env, doctors, xray, surgery))
    env.process(manage_doctors(env, doctors))

    # Run simulation
    while env.now < SIM_DURATION:
        with stats_lock:
            times.append(env.now)
            patients_in_system.append(current_patients[0])
            waiting_queue.append(current_waiting[0])
            patient_type_count.append(dict(type_counter))
        env.step()

# Animation update function
def animate(i):
    ax1.clear()
    ax2.clear()
    ax3.clear()

    ax1.plot(times, patients_in_system, label='Patients in System', color='blue')
    ax1.set_ylabel("Patients in System")
    ax1.set_ylim(0, max(5, max(patients_in_system, default=1)))
    ax1.legend()
    ax1.grid(True)

    ax2.plot(times, waiting_queue, label='Waiting Queue Length', color='red')
    ax2.set_ylabel("Waiting Patients")
    ax2.set_xlabel("Simulation Time (min)")
    ax2.set_ylim(0, max(3, max(waiting_queue, default=1)))
    ax2.legend()
    ax2.grid(True)

    if patient_type_count:
        counts = patient_type_count[-1]
        labels = list(PATIENT_TYPES.keys())
        values = [counts.get(pt, 0) for pt in labels]
        ax3.bar(labels, values, color=['red', 'orange', 'green'])
        ax3.set_ylabel("In Treatment")
        ax3.set_title("Patient Type Counts")
        ax3.grid(True)

# Save logs to CSV after simulation ends
def save_logs_to_csv():
    keys = ['Name', 'Type', 'Arrival', 'Departure', 'WaitTime', 'TotalTime']
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(patient_logs)
    print(f"Patient logs saved to '{csv_file}'")

# Run sim in a thread, then start plot animation
def simulation_thread():
    run_simulation()
    save_logs_to_csv()

# Plot setup
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 10))
plt.tight_layout()

ani = animation.FuncAnimation(fig, animate, interval=200)

# Start simulation thread
sim_thread = Thread(target=simulation_thread)
sim_thread.start()

plt.show()

# Wait for thread to finish before exiting script
sim_thread.join()
