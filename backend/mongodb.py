


from pymongo import MongoClient


Client = None


"""
Establish a global MongoDB connection.

Parameters:
    dbAddress (str, optional): Hostname or IP when not using URI.
    dbPort    (int, optional): Port when not using URI.
    uri (str, optional): Full connection string (e.g. mongodb://localhost:27017/). Takes precedence over address/port.

Returns:
    None
"""
def Connect(dbAddress=None, dbPort=None, uri=None):
    global Client
    if Client is None:
        try:
            if uri:
                Client = MongoClient(uri)
            elif dbAddress is not None and dbPort is not None:
                Client = MongoClient(f"mongodb://{dbAddress}:{dbPort}")
            else:
                Client = MongoClient("mongodb://localhost:27017/")
            print("MongoDB connection established.")
        except Exception as e:
            print(f"Error connecting to MongoDB: {str(e)}")
            Client = None 


"""
Get a MongoDB collection object.

Parameters:
    dbName (str): Name of the MongoDB database.
    collectionName (str): Name of the collection to access.

Returns:
    Collection: A PyMongo Collection object that can be used for CRUD operations.
"""
def GetCollection(dbName, collectionName):
    global Client
    if Client is None:
        raise ValueError("Database connection is not established. Call connect() first.")
    database = Client[dbName]
    return database[collectionName]