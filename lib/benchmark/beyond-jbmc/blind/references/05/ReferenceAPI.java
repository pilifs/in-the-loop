import org.apache.uima.collection.impl.metadata.cpe.CpeDescriptorFactory;
import org.apache.uima.collection.metadata.*;
public final class ReferenceAPI {
    public static long primary(int n) {
        try {
            CpeCasProcessors list=CpeDescriptorFactory.produceCasProcessors();
            CpeCasProcessor a=CpeDescriptorFactory.produceCasProcessor("first"), b=CpeDescriptorFactory.produceCasProcessor("second");
            list.addCpeCasProcessor(a);list.addCpeCasProcessor(b,n);
            if (list.getCpeCasProcessor(n)!=b || list.getCpeCasProcessor(1-n)!=a) return 0;
            list.removeCpeCasProcessor(n);
            return list.getAllCpeCasProcessors().length==1 && list.getCpeCasProcessor(0)==a?1:0;
        } catch(CpeDescriptorException e){throw new IllegalStateException(e);}
    }
    public static long control(int n) {
        try {CpeCasProcessors list=CpeDescriptorFactory.produceCasProcessors();list.setOutputQueueSize(n+1);
             return list.getOutputQueueSize()==n+1 && list.getAllCpeCasProcessors().length==0?1:0;}
        catch(CpeDescriptorException e){throw new IllegalStateException(e);}
    }
}
