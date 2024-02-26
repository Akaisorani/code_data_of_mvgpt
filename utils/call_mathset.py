# Import module
import jpype

# Enable Java imports
import jpype.imports

# Pull in types
from jpype.types import *

# Launch the JVM
# jpype.startJVM()

# import java.lang

# from com.alimama.ad.ltp.fusion.engine.ast.expression import Expression

def query_by_jpype():
    # if not jpype.isJVMStarted():
    #     jvmPath = jpype.getDefaultJVMPath() 
    #     print("getDefaultJVMPath", jvmPath)
    #     jpype.startJVM(classpath=[jvmPath])
    # if not jpype.isThreadAttachedToJVM():
    #     jpype.attachThreadToJVM()
    try:
        jpype.java.lang.System.out.println( " hello world! " ) 
        # java_class = jpype.JClass('com.xxx.xxx')
        # result = java_class.someStaticFunction(some_param)
        result="123"
    except Exception as e:
        print(e)
        result = None
    finally:
        #jpype.shutdownJVM()
        return result

def query_jar():
    jarpath='./utils/mathset-1.0-SNAPSHOT-jar-with-dependencies.jar'
    jpype.startJVM(jpype.getDefaultJVMPath(), "-ea", "-Djava.class.path={0}".format(jarpath))
    Test=jpype.JClass('example.Example')
    test=Test()

    qm={'sql1':'a','sql2':'a or b'}
    res=test.contains("a IN ('1', '2') or b IN ('3')", "a IN ('1', '2') or b")
    print(res)

    jpype.shutdownJVM()



if __name__=="__main__":
    # query_by_jpype()
    query_jar()

