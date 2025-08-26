

class Warehouse(object):

    def __init__(self, env, type_id, instance_id):
        """
        Initializes a warehouse object
        
        Parameters:
        - env (simpy.Environment): The simulation environment.
        - type_id (str): The type of the warehouse.
        - instance_id (int): The instance ID of the warehouse.

        """
        self.env = env
        self.type_id = type_id
        self.instance_id = instance_id

        self.id = f"{type_id}-{instance_id}"
        self.stock = []

    def add_item(self, produced_component):
        """
        Adds an item to the warehouse's stock.
        """
        self.stock.append(produced_component)
        
    
        