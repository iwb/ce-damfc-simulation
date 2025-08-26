import simpy
import numpy as np
import sys

from workstation import Workstation
from warehouse import Warehouse
from preShopPool import PreShopPool
from orderReleaseControl import ORControlSystem
from kpiTracker import KPITracker
from processCSV import ProcessCSV

from loggerConfig import log_manager
from appConfig import app_config, order_generator


class MainSimulation:
    def __init__(self, env):
        """
        Initializes the simulation environment and other necessary objects.

        Parameters:
        - env (simpy.Environment): The simulation environment.
        """
        self.env = env
        self.station_list = []
        self.warehouse_list = []

    def create_stations_and_warehouses(self):
        """
        This method is used to create workstations and an output warehouse.
        """
        types = app_config.STATION_TYPES  # 5 type station
        instances_per_type = (
            app_config.STATION_INSTANCES
        )  # number of instances per type
        for type_id in types:
            for instance_id in range(1, instances_per_type[type_id] + 1):
                ws = Workstation(self.env, type_id, instance_id)
                self.station_list.append(ws)
                log_manager.main_logger.info(f"Create {ws}")

        output_warehouse = Warehouse(
            self.env, "output", "warehouse"
        )  # create the output warehouse
        self.warehouse_list.append(output_warehouse)
        log_manager.main_logger.info(f"Create {output_warehouse}")


def start_order_generate(env, orControlSystem, orders):
    """
    This method is used to generate jobs in Simpy environment according to the inter-arrival time.
    Note: A job appears at a specific time point and is added to the environment and the job list at that moment.

    Parameters:
        env (simpy.Environment): The simulation environment
        job_list (list): The list of jobs that is used by the pre-shop pool
        jobs (list): The list of jobs that will be generated
    """
    for order in orders:
        arrival_time = order.arrival_time
        yield env.timeout(arrival_time - env.now)
        orControlSystem.add_order(order)


def run_simulation(
    env,
    simulation_id,
    simulation_time,
    workload_norm,
    pool_rule,
    dispatching_rule,
    kpi_tracker,
):
    """
    Runs a simulation with the given pool sequencing and dispatching rule.
    Stores KPI results after the simulation.
    """
    log_manager.set_simulation_info(simulation_id, f"{pool_rule} + {dispatching_rule}")

    # Initialize main simulation
    main_simulation = MainSimulation(env)
    main_simulation.create_stations_and_warehouses()

    # Initialize lists for stations and warehouses
    station_list = main_simulation.station_list
    warehouse_list = main_simulation.warehouse_list
    preShopPool = PreShopPool(env)

    # Initialize the order generator and generate all orders
    np.random.seed(44)
    all_orders = order_generator.generate_orders()
    log_manager.set_orders(all_orders)

    # Initialize the Order Release Control System
    myORControlSystem = ORControlSystem(
        env, preShopPool, station_list, warehouse_list, workload_norm, pool_rule
    )

    # Start the simulation: add orders to the preShopPool based on their arrival time
    env.process(start_order_generate(env, myORControlSystem, all_orders))

    # Start order release control with LUMS COR
    myORControlSystem.order_release_with_lums_cor(round_time=4)

    # Link each station to the order release control system and start processing
    for ws in station_list:
        ws.orControlSystem = myORControlSystem
        ws.dispatching_rule = dispatching_rule
        env.process(ws.start_processing())

    # Run the simulation for certain time units
    log_manager.log_event(0.0, "N/A", "N/A", "N/A", "Simulation Start", "N/A")
    env.run(until=simulation_time)
    log_manager.log_event(simulation_time, "N/A", "N/A", "N/A", "Simulation End", "N/A")

    # Finalize the simulation by logging the work/idle time of each station
    for station in station_list:
        if not station.idle:
            work_duration = simulation_time - station.last_work_start
            station.total_work_time += work_duration
        else:
            idle_duration = simulation_time - station.last_idle_start
            station.total_idle_time += idle_duration

        log_manager.log_event(
            simulation_time,
            station.id,
            "N/A",
            "N/A",
            "Simulation End",
            f"FWT: {station.total_work_time:.2f}, FIT: {station.total_idle_time:.2f}",
        )

    log_manager.record_current_simulation_data(
        simulation_id, f"{pool_rule} + {dispatching_rule}", all_orders, station_list
    )

    # Store KPI results for this simulation run
    kpi_tracker.store_kpi_results(
        simulation_id,
        f"{pool_rule} + {dispatching_rule}",
        simulation_time,
        workload_norm,
        all_orders,
        station_list,
    )

    print(f"Simulation with {pool_rule} + {dispatching_rule} completed.")


if __name__ == "__main__":
    # Set parameters for simulation
    simulation_time = app_config.SIMULATION_TIME
    norm_load = app_config.WORKLOAD_NORM

    # Initialize KPI Tracker and CSV Processor
    kpi_tracker = KPITracker()
    csv_processor = ProcessCSV()

    # Check if executed with appConfig settings for individual scenario or all 9 scenarios
    if len(sys.argv) > 1 and sys.argv[1] == "--single":
        # Run single simulation with appConfig settings
        print("\n" + "=" * 60)
        print("Running SINGLE simulation with appConfig settings:")
        print(f"  Pool Rule: {app_config.POOL_SEQUENCING_RULE}")
        print(f"  Dispatch Rule: {app_config.DISPATCHING_RULE}")
        print("=" * 60 + "\n")

        env = simpy.Environment()
        run_simulation(
            env,
            "ConfigRun",
            simulation_time,
            norm_load,
            app_config.POOL_SEQUENCING_RULE,
            app_config.DISPATCHING_RULE,
            kpi_tracker,
        )
    else:
        # Run all 9 scenarios using the SCENARIOS list from appConfig
        print("\n" + "=" * 60)
        print("Running ALL 9 SCENARIOS from the paper")
        print("=" * 60)

        # Use the SCENARIOS list from appConfig
        for scenario in app_config.SCENARIOS:
            env = simpy.Environment()
            run_simulation(
                env,
                scenario["id"],
                simulation_time,
                norm_load,
                scenario["pool"],
                scenario["dispatch"],
                kpi_tracker,
            )

        print("\nAll simulations completed and results compared.")

    # Save and display results
    log_manager.save_to_csv()
    csv_processor.process_and_save_logs()
    log_manager.display_full_event_log_in_frame()
    kpi_tracker.display_combined_results()
