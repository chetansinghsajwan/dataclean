from pyspark.sql import DataFrame as SparkSqlDataFrame, SparkSession as SparkSqlSession
from pyspark.sql.connect.dataframe import DataFrame as SparkConnectDataFrame
from pyspark.sql.connect.session import SparkSession as SparkConnectSession

SparkSession = SparkSqlSession | SparkConnectSession
SparkDataFrame = SparkSqlDataFrame | SparkConnectDataFrame
