package si;

/** A subclass of the wrapper that overrides nothing: a stand-in for Wrapper's receivers does not cover it. */
public class Loud extends Wrapper {

	public Loud(Object target) {
		super(target);
	}
}
