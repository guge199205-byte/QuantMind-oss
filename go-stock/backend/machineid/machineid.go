package machineid

import (
	"fmt"
	"runtime"

	machineidlib "github.com/denisbrodbeck/machineid"
)

var buildKey string

func Init(key string) {
	buildKey = key
}

func GetMachineId() string {
	salt := buildKey
	if salt == "" {
		salt = "cc1e0d684e32f176c56ff1fcf384dcd9"
	}

	id, err := machineidlib.ProtectedID(salt)
	if err != nil {
		id, err = machineidlib.ID()
		if err != nil {
			return fmt.Sprintf("fallback-%s-%d", runtime.GOOS, 0)
		}
	}

	return id
}
