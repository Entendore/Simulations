import simpy
import random
import statistics
import matplotlib.pyplot as plt
from collections import defaultdict

# Constants
RANDOM_SEED = 42
SIM_TIME = 100  # Minutes

# Patient types and priorities
PATIENT_TYPES = {
    'Critical': {'priority': 0, 'xray': True, 'surgery': True, 'treat_time': 15},
    'Moderate': {'priority': 1, 'xray': True, 'surgery': False, 'treat_time': 10},
    'Mild':     {'priority': 2, 'xray': False, 'surgery': False, 'treat_time': 5}
}

STAFF = {
    'doctors': 2,
    'xray_machines': 1,
    'surgery_rooms': 1
}

# Metrics
wait_times = []
system_times = []
type_distribution = defaultdict(int)
per_patient_times = []

# Patient process
def patient(env, name, ptype, doctors, xray, surgery):
    data = PATIENT_TYPES[ptype]
    priority = data['priority']
    arrival = env.now
    type_distribution[ptype] += 1

    # Triage delay
    yield env.timeout(random.uniform(1, 2))

    with doctors.request(priority=priority) as req:
        start_wait = env.now
        yield req
        wait = env.now - start_wait
        wait_times.append(wait)

        yield env.timeout(data['treat_time'])

    # X-Ray (optional)
    if data['xray']:
        with xray.request() as req:
            yield req
            yield env.timeout(random.uniform(5, 8))

    # Surgery (optional)
    if data['surgery']:
        with surgery.request() as req:
            yield req
            yield env.timeout(random.uniform(10, 15))

    system_time = env.now - arrival
    system_times.append(system_time)
    per_patient_times.append((env.now, ptype, system_time))

# Patient generator
def patient_generator(env, doctors, xray, surgery):
    i = 0
    while True:
        yield env.timeout(random.uniform(1, 4))
        i += 1
        ptype = random.choices(
            population=list(PATIENT_TYPES.keys()),
            weights=[1, 2, 4]
        )[0]
        env.process(patient(env, f'Patient {i}', ptype, doctors, xray, surgery))

# Run the simulation
def run_simulation():
    random.seed(RANDOM_SEED)
    env = simpy.Environment()

    doctors = simpy.PriorityResource(env, capacity=STAFF['doctors'])
    xray = simpy.Resource(env, capacity=STAFF['xray_machines'])
    surgery = simpy.Resource(env, capacity=STAFF['surgery_rooms'])

    env.process(patient_generator(env, doctors, xray, surgery))
    env.run(until=SIM_TIME)

run_simulation()


# Plotting results
def plot_results():
    fig, axs = plt.subplots(3, 1, figsize=(10, 12))
    fig.suptitle("Healthcare System Simulation Results", fontsize=16)

    # 1. Wait Time Histogram
    axs[0].hist(wait_times, bins=10, color='skyblue', edgecolor='black')
    axs[0].set_title("Wait Time Distribution")
    axs[0].set_xlabel("Wait Time (minutes)")
    axs[0].set_ylabel("Number of Patients")

    # 2. System Time Scatter (by Patient Type)
    colors = {'Critical': 'red', 'Moderate': 'orange', 'Mild': 'green'}
    for time, ptype, system_time in per_patient_times:
        axs[1].scatter(time, system_time, label=ptype, color=colors[ptype], alpha=0.7)

    axs[1].set_title("System Time by Patient Type")
    axs[1].set_xlabel("Simulation Time (minutes)")
    axs[1].set_ylabel("System Time (minutes)")
    axs[1].legend()

    # 3. Patient Type Distribution
    axs[2].bar(type_distribution.keys(), type_distribution.values(), color=['red', 'orange', 'green'])
    axs[2].set_title("Patient Type Distribution")
    axs[2].set_ylabel("Count")

    plt.tight_layout()
    plt.show()

plot_results()
